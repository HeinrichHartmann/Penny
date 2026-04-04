"""Replay engine - rebuild state from archived imports and mutations."""

from __future__ import annotations

from dataclasses import dataclass

from penny.config import default_db_path
from penny.db import transaction
from penny.vault.apply import apply_entry, apply_mutation
from penny.vault.config import VaultConfig
from penny.vault.log import LogManager
from penny.vault.mutations import MutationLog
from penny.vault.rules_store import latest_rules_path


@dataclass
class ReplayResult:
    """Result of a vault replay operation."""

    entries_processed: int
    entries_by_type: dict[str, int]

    def __repr__(self) -> str:
        return f"ReplayResult(entries={self.entries_processed}, types={self.entries_by_type})"


class ReplayEngine:
    """Rebuild the SQLite projection from portable storage artifacts."""

    def __init__(self, config: VaultConfig | None = None):
        if config is None:
            config = VaultConfig()
        self.config = config
        self.log = LogManager(config)

    def replay(self) -> ReplayResult:
        """Replay all log entries and rebuild database.

        Clears existing database and rebuilds from vault log.

        Returns:
            ReplayResult with counts of entries processed.
        """
        from penny.db import init_db, init_default_db

        # Drop any existing projection so replay is deterministic against drift.
        db_path = default_db_path()
        init_db(None)
        if db_path.exists():
            db_path.unlink()

        # Rebuild the file-backed projection from the current PENNY_DATA_DIR.
        init_default_db()

        entries_processed = 0
        entries_by_type: dict[str, int] = {}

        for entry in self.log.iter_entries():
            apply_entry(entry)
            entries_processed += 1

            manifest = entry.read_manifest()
            entry_type = manifest.type
            entries_by_type[entry_type] = entries_by_type.get(entry_type, 0) + 1

        _ensure_projection_state()
        _set_last_applied_mutation_seq(0)
        mutation_result = apply_pending_mutations(self.config)
        entries_processed += mutation_result.entries_processed
        for entry_type, count in mutation_result.entries_by_type.items():
            entries_by_type[entry_type] = entries_by_type.get(entry_type, 0) + count

        _restore_runtime_classifications(self.config)

        return ReplayResult(
            entries_processed=entries_processed,
            entries_by_type=entries_by_type,
        )


def _ensure_projection_state() -> None:
    with transaction() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projection_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )


def _get_last_applied_mutation_seq() -> int:
    _ensure_projection_state()
    with transaction() as conn:
        row = conn.execute(
            "SELECT value FROM projection_state WHERE key = 'last_applied_mutation_seq'"
        ).fetchone()
        return int(row["value"]) if row is not None else 0


def _set_last_applied_mutation_seq(seq: int) -> None:
    _ensure_projection_state()
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO projection_state (key, value)
            VALUES ('last_applied_mutation_seq', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(seq),),
        )


def apply_pending_mutations(
    config: VaultConfig | None = None,
    *,
    upto_seq: int | None = None,
) -> ReplayResult:
    """Apply unapplied mutation rows to the current projection."""
    cfg = config or VaultConfig()
    last_applied = _get_last_applied_mutation_seq()
    entries_processed = 0
    entries_by_type: dict[str, int] = {}

    for row in MutationLog(cfg).list_rows():
        if row.seq <= last_applied:
            continue
        if upto_seq is not None and row.seq > upto_seq:
            break
        apply_mutation(row)
        _set_last_applied_mutation_seq(row.seq)
        last_applied = row.seq
        entries_processed += 1
        entries_by_type[row.type] = entries_by_type.get(row.type, 0) + 1

    return ReplayResult(entries_processed=entries_processed, entries_by_type=entries_by_type)


def _restore_runtime_classifications(config: VaultConfig) -> None:
    """Recompute runtime-only classifications from the latest rules snapshot.

    Classification results are intentionally not persisted in the mutation log,
    so replay needs to rebuild them after the projection has been restored.
    """
    rules_path = latest_rules_path(config)
    if rules_path is None or not rules_path.exists():
        return

    from penny.classify import load_rules_config, run_classification_pass
    from penny.transactions import list_transactions
    from penny.vault.writes import apply_classifications

    rules_config = load_rules_config(rules_path)
    transactions = list_transactions(limit=None, neutralize=False)
    if not transactions:
        return

    result = run_classification_pass(transactions, rules_config)
    apply_classifications(result.decisions, config=config)


def replay_vault(config: VaultConfig | None = None) -> ReplayResult:
    """Convenience function to replay vault and rebuild database.

    Args:
        config: Optional vault config (uses default if not provided)

    Returns:
        ReplayResult with counts of entries processed.
    """
    engine = ReplayEngine(config)
    return engine.replay()
