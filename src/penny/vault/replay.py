"""Replay engine - rebuild state from vault log."""

from __future__ import annotations

from dataclasses import dataclass

from penny.config import default_db_path
from penny.vault.config import VaultConfig
from penny.vault.log import LogManager
from penny.vault.apply import apply_entry


@dataclass
class ReplayResult:
    """Result of a vault replay operation."""

    entries_processed: int
    entries_by_type: dict[str, int]

    def __repr__(self) -> str:
        return f"ReplayResult(entries={self.entries_processed}, types={self.entries_by_type})"


class ReplayEngine:
    """Replays vault log entries to rebuild SQLite projection.

    The replay engine iterates through all log entries in sequence order
    and applies each one to rebuild the database state.
    """

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

            # Track by base type (e.g., "ingest" from "ingest_comdirect")
            manifest = entry.read_manifest()
            entry_type = manifest.type
            entries_by_type[entry_type] = entries_by_type.get(entry_type, 0) + 1

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
