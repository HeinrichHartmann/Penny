"""Replay engine - rebuild state from vault log."""

from __future__ import annotations

from typing import TYPE_CHECKING

from penny.vault.config import VaultConfig
from penny.vault.log import LogManager
from penny.vault.apply import apply_entry

if TYPE_CHECKING:
    pass


class ReplayEngine:
    """Replays vault log entries to rebuild SQLite projection.

    The replay engine iterates through all log entries in sequence order
    and applies each one to rebuild the database state.
    """

    def __init__(self, config: VaultConfig | None = None, in_memory: bool = False):
        if config is None:
            config = VaultConfig()
        self.config = config
        self.log = LogManager(config)
        self.in_memory = in_memory

    def replay(self) -> ReplayResult:
        """Replay all log entries and rebuild database.

        Returns:
            ReplayResult with counts of entries processed.
        """
        from penny.db import init_db, reset_db

        # Start fresh - clear any existing database state
        reset_db()

        # Initialize fresh database with schema
        if self.in_memory:
            init_db(None)  # in-memory for tests
        else:
            init_db(self.config.db_path)  # use config path

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


class ReplayResult:
    """Result of a vault replay operation."""

    def __init__(self, entries_processed: int, entries_by_type: dict[str, int]):
        self.entries_processed = entries_processed
        self.entries_by_type = entries_by_type

    def __repr__(self) -> str:
        return f"ReplayResult(entries={self.entries_processed}, types={self.entries_by_type})"


def replay_vault(
    config: VaultConfig | None = None,
    in_memory: bool = False,
) -> ReplayResult:
    """Convenience function to replay vault and rebuild database.

    Args:
        config: Optional vault config (uses default if not provided)
        in_memory: If True, use in-memory database (for tests)

    Returns:
        ReplayResult with counts of entries processed.
    """
    engine = ReplayEngine(config, in_memory=in_memory)
    return engine.replay()
