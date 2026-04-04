"""Database connection and schema management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from penny.accounts.storage import default_db_path

_db_path: Path | None = None


def set_db_path(path: Path | None) -> None:
    """Set the database path (for testing). Pass None to reset to default."""
    global _db_path
    _db_path = path


def get_db_path() -> Path:
    """Get the database path."""
    if _db_path is not None:
        return _db_path
    return default_db_path()


def connect() -> sqlite3.Connection:
    """Get a database connection."""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction():
    """Context manager for database transactions."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    """Initialize database schema."""
    with transaction() as conn:
        # Accounts table (from AccountStorage)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank TEXT NOT NULL,
                bank_account_number TEXT,
                display_name TEXT,
                iban TEXT,
                hidden INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS account_identifiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL REFERENCES accounts(id),
                identifier_type TEXT NOT NULL,
                identifier_value TEXT NOT NULL,
                UNIQUE(identifier_type, identifier_value)
            );
            """
        )

        # Transactions table
        conn.executescript(
            """
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

        # Ensure group_id is never NULL
        conn.execute("UPDATE transactions SET group_id = fingerprint WHERE group_id IS NULL")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column if it doesn't exist (migration helper)."""
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
