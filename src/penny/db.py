"""Database connection and schema management."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from penny.config import default_db_path


# Table ownership model:
# - `transactions` is a projection table. API handlers must not mutate it directly.
#   It is updated only by vault apply/replay flows and runtime classification passes.
# - `accounts` is mixed ownership. User-editable metadata may change through sanctioned
#   mutation APIs, while derived state should still be treated as projection-backed.
# - `account_identifiers` and `subaccounts` are vault-owned structural tables.


class Database:
    """Database connection manager.

    Args:
        path: Database file path, or None for in-memory database.
    """

    def __init__(self, path: Path | None = None):
        self.path = path
        # For in-memory databases, keep one connection alive to persist data
        self._keeper: sqlite3.Connection | None = None
        if path is None:
            self._keeper = self._create_connection()

    def _create_connection(self) -> sqlite3.Connection:
        if self.path is None:
            # Shared cache allows multiple connections to same in-memory db
            conn = sqlite3.connect("file::memory:?cache=shared", uri=True)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def connect(self) -> sqlite3.Connection:
        """Get a new database connection."""
        return self._create_connection()

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Initialize database schema."""
        with self.transaction() as conn:
            conn.executescript(
                """
                -- Mixed-ownership table. User-facing account metadata may be updated
                -- through sanctioned mutation APIs; derived fields remain projection-backed.
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank TEXT NOT NULL,
                    display_name TEXT,
                    iban TEXT,
                    holder TEXT,
                    notes TEXT,
                    balance_cents INTEGER,
                    balance_date TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    hidden INTEGER DEFAULT 0
                );

                -- Vault-owned structural tables. These are updated through vault apply flows.
                CREATE TABLE IF NOT EXISTS account_identifiers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    identifier_type TEXT NOT NULL,
                    identifier_value TEXT NOT NULL,
                    UNIQUE(account_id, identifier_type, identifier_value)
                );

                CREATE TABLE IF NOT EXISTS subaccounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    type TEXT NOT NULL,
                    display_name TEXT,
                    UNIQUE(account_id, type)
                );

                -- Projection table. Do not mutate directly from API handlers.
                -- This table is populated by vault apply/replay flows and runtime
                -- reclassification against the active rules snapshot.
                CREATE TABLE IF NOT EXISTS transactions (
                    fingerprint TEXT PRIMARY KEY,
                    account_id INTEGER NOT NULL REFERENCES accounts(id),
                    subaccount_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    payee TEXT NOT NULL,
                    memo TEXT NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    value_date TEXT,
                    transaction_type TEXT,
                    reference TEXT,
                    raw_buchungstext TEXT,
                    raw_row TEXT,
                    category TEXT,
                    classification_rule TEXT,
                    classified_at TEXT,
                    imported_at TEXT NOT NULL,
                    source_file TEXT,
                    group_id TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
                CREATE INDEX IF NOT EXISTS idx_transactions_payee ON transactions(payee);
                CREATE INDEX IF NOT EXISTS idx_transactions_group ON transactions(group_id);
                """
            )
            conn.execute("UPDATE transactions SET group_id = fingerprint WHERE group_id IS NULL")

    def close(self) -> None:
        """Close the database (releases in-memory keeper connection)."""
        if self._keeper:
            self._keeper.close()
            self._keeper = None


# Module-level instance
_instance: Database | None = None


def init_db(path: Path | None = None) -> Database:
    """Initialize the database. Call once at startup.

    Args:
        path: Database file path. None for in-memory (tests).
              If not provided, uses default_db_path().
    """
    global _instance
    if _instance is not None:
        _instance.close()

    # Use sentinel to distinguish "not provided" from "explicitly None"
    if path is None:
        _instance = Database(None)  # in-memory
    else:
        _instance = Database(path)

    _instance.init_schema()
    return _instance


def init_default_db() -> Database:
    """Initialize database at default path from PENNY_DATA_DIR.

    Forces file-based database. Use this for CLI/production.
    """
    return init_db(default_db_path())


def get_db() -> Database:
    """Get the database instance. Auto-initializes with default path if needed.

    Re-initializes if default path changed (e.g., PENNY_DATA_DIR changed).
    Does not re-init if instance was explicitly set to in-memory (path=None).
    """
    global _instance
    if _instance is None:
        # No instance - auto-initialize with default path
        path = default_db_path()
        _instance = Database(path)
        _instance.init_schema()
    elif _instance.path is not None:
        # File-based instance - check if path changed
        path = default_db_path()
        if _instance.path != path:
            _instance.close()
            _instance = Database(path)
            _instance.init_schema()
    # If path is None (in-memory), keep the existing instance
    return _instance


# Convenience functions that delegate to the instance
def connect() -> sqlite3.Connection:
    """Get a database connection."""
    return get_db().connect()


@contextmanager
def transaction():
    """Context manager for database transactions."""
    with get_db().transaction() as conn:
        yield conn


def init_schema() -> None:
    """Initialize database schema."""
    get_db().init_schema()
