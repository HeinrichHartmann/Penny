"""Replay engine - rebuild state from archived imports and mutations."""

from __future__ import annotations

import json
from dataclasses import dataclass

from penny.config import default_db_path
from penny.vault.config import VaultConfig
from penny.vault.log import LogManager
from penny.vault.mutations import MutationLog
from penny.vault.rules_store import latest_rules_path
from penny.vault.apply import apply_ingest


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
            apply_ingest(entry)
            entries_processed += 1

            manifest = entry.read_manifest()
            entry_type = manifest.type
            entries_by_type[entry_type] = entries_by_type.get(entry_type, 0) + 1

        for row in MutationLog(self.config).list_rows():
            payload = json.loads(row.payload_json)

            if row.type == "account_updated":
                from penny.accounts import update_account_metadata

                update_account_metadata(int(row.entity_id), **payload)
                entries_processed += 1
                entries_by_type[row.type] = entries_by_type.get(row.type, 0) + 1
            elif row.type == "rules_updated":
                from penny.api.rules import run_rules_path

                rules_path = self.config.rules_dir / payload["path"]
                if rules_path.exists():
                    run_rules_path(rules_path)
                    entries_processed += 1
                    entries_by_type[row.type] = entries_by_type.get(row.type, 0) + 1

        return ReplayResult(
            entries_processed=entries_processed,
            entries_by_type=entries_by_type,
        )


def replay_vault(config: VaultConfig | None = None) -> ReplayResult:
    """Convenience function to replay vault and rebuild database.

    Args:
        config: Optional vault config (uses default if not provided)

    Returns:
        ReplayResult with counts of entries processed.
    """
    engine = ReplayEngine(config)
    return engine.replay()
