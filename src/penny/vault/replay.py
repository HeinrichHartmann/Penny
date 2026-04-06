"""Replay engine - rebuild state from vault ledger."""

from __future__ import annotations

from dataclasses import dataclass

from penny.config import default_db_path
from penny.db import transaction
from penny.runtime_rules import run_stored_rules
from penny.vault.apply import apply_entry
from penny.vault.config import VaultConfig
from penny.vault.ledger import Ledger


@dataclass
class ReplayResult:
    """Result of a vault replay operation."""

    entries_processed: int
    entries_by_type: dict[str, int]

    def __repr__(self) -> str:
        return f"ReplayResult(entries={self.entries_processed}, types={self.entries_by_type})"


class ReplayEngine:
    """Rebuild the SQLite projection from vault ledger."""

    def __init__(self, config: VaultConfig | None = None):
        if config is None:
            config = VaultConfig()
        self.config = config
        self.ledger = Ledger(config.path)

    def replay(self) -> ReplayResult:
        """Replay all ledger entries and rebuild database.

        Clears existing database and rebuilds from vault ledger.
        All entry types (ingest, rules, balance, mutation) are processed
        in sequence order from history.tsv.

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

        # Replay all enabled entries from history.tsv (includes mutations now)
        for entry in self.ledger.read_entries():
            if entry.enabled:
                apply_entry(entry, self.config)
                entries_processed += 1
                entries_by_type[entry.entry_type] = entries_by_type.get(entry.entry_type, 0) + 1

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


def _get_last_applied_seq() -> int:
    """Get the last applied ledger sequence number."""
    _ensure_projection_state()
    with transaction() as conn:
        row = conn.execute(
            "SELECT value FROM projection_state WHERE key = 'last_applied_seq'"
        ).fetchone()
        return int(row["value"]) if row is not None else 0


def _set_last_applied_seq(seq: int) -> None:
    """Set the last applied ledger sequence number."""
    _ensure_projection_state()
    with transaction() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO projection_state (key, value)
            VALUES ('last_applied_seq', ?)
            """,
            (str(seq),),
        )


def apply_pending_mutations(
    config: VaultConfig | None = None, *, upto_seq: int | None = None
) -> ReplayResult:
    """Apply new ledger entries since last applied.

    Args:
        config: Vault configuration.
        upto_seq: If provided, only apply entries up to this sequence number.
    """
    if config is None:
        config = VaultConfig()

    ledger = Ledger(config.path)
    last_applied = _get_last_applied_seq()

    entries_processed = 0
    entries_by_type: dict[str, int] = {}

    for entry in ledger.read_entries():
        if entry.sequence <= last_applied:
            continue
        if upto_seq is not None and entry.sequence > upto_seq:
            break
        if not entry.enabled:
            continue
        apply_entry(entry, config)
        entries_processed += 1
        entries_by_type[entry.entry_type] = entries_by_type.get(entry.entry_type, 0) + 1
        _set_last_applied_seq(entry.sequence)

    return ReplayResult(
        entries_processed=entries_processed,
        entries_by_type=entries_by_type,
    )


def _restore_runtime_classifications(config: VaultConfig) -> None:
    """Restore runtime classifications from latest rules snapshot."""
    run_stored_rules(config=config)


def replay_vault(config: VaultConfig | None = None) -> ReplayResult:
    """Convenience function to replay the vault."""
    engine = ReplayEngine(config)
    return engine.replay()
