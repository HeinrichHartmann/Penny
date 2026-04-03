"""SQLite-backed account storage."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path

from penny.accounts.models import Account, Subaccount


def default_data_dir() -> Path:
    """Return Penny's data directory."""

    override = os.environ.get("PENNY_DATA_DIR")
    if override:
        return Path(override).expanduser()

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser() / "penny"

    return Path.home() / ".local" / "share" / "penny"


def default_db_path() -> Path:
    """Return the default SQLite database path."""

    return default_data_dir() / "penny.db"


class AccountStorage:
    """Persistence layer for accounts."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path) if db_path is not None else default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
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
                """
            )
            conn.commit()

    def create_account(
        self,
        *,
        bank: str,
        bank_account_numbers: list[str] | None = None,
        display_name: str | None = None,
        iban: str | None = None,
        holder: str | None = None,
        notes: str | None = None,
        balance_cents: int | None = None,
        balance_date: date | None = None,
        subaccounts: dict[str, Subaccount] | None = None,
    ) -> Account:
        """Create and persist an account."""

        now = datetime.now()
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO accounts (
                    bank, display_name, iban, holder, notes,
                    balance_cents, balance_date, created_at, updated_at, hidden
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    bank,
                    display_name,
                    iban,
                    holder,
                    notes,
                    balance_cents,
                    balance_date.isoformat() if balance_date else None,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            account_id = cursor.lastrowid

            for account_number in bank_account_numbers or []:
                conn.execute(
                    """
                    INSERT INTO account_identifiers (account_id, identifier_type, identifier_value)
                    VALUES (?, 'bank_account_number', ?)
                    """,
                    (account_id, account_number),
                )

            for subaccount in (subaccounts or {}).values():
                conn.execute(
                    """
                    INSERT INTO subaccounts (account_id, type, display_name)
                    VALUES (?, ?, ?)
                    """,
                    (account_id, subaccount.type, subaccount.display_name),
                )

            conn.commit()

        account = self.get_account(account_id, include_hidden=True)
        if account is None:
            raise RuntimeError(f"Account {account_id} was not persisted")
        return account

    def list_accounts(self, *, include_hidden: bool = False) -> list[Account]:
        """Return all accounts."""

        with closing(self._connect()) as conn:
            query = "SELECT id FROM accounts"
            params: list[object] = []
            if not include_hidden:
                query += " WHERE hidden = 0"
            query += " ORDER BY id"
            ids = [row["id"] for row in conn.execute(query, params).fetchall()]
        return [account for account_id in ids if (account := self.get_account(account_id, include_hidden=True))]

    def get_account(self, account_id: int, *, include_hidden: bool = True) -> Account | None:
        """Return an account by ID."""

        with closing(self._connect()) as conn:
            query = "SELECT * FROM accounts WHERE id = ?"
            params: list[object] = [account_id]
            if not include_hidden:
                query += " AND hidden = 0"
            row = conn.execute(query, params).fetchone()
            if row is None:
                return None
            return self._hydrate_account(conn, row)

    def soft_delete_account(self, account_id: int) -> bool:
        """Hide an account without removing it."""

        with closing(self._connect()) as conn:
            cursor = conn.execute(
                """
                UPDATE accounts
                SET hidden = 1, updated_at = ?
                WHERE id = ? AND hidden = 0
                """,
                (datetime.now().isoformat(), account_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def find_account_by_bank_account_number(
        self,
        bank: str,
        account_number: str,
        *,
        include_hidden: bool = True,
    ) -> Account | None:
        """Find an account by bank and bank account number."""

        with closing(self._connect()) as conn:
            query = """
                SELECT a.*
                FROM accounts a
                JOIN account_identifiers ai ON ai.account_id = a.id
                WHERE a.bank = ?
                  AND ai.identifier_type = 'bank_account_number'
                  AND ai.identifier_value = ?
            """
            params: list[object] = [bank, account_number]
            if not include_hidden:
                query += " AND a.hidden = 0"
            query += " ORDER BY a.id LIMIT 1"
            row = conn.execute(query, params).fetchone()
            if row is None:
                return None
            return self._hydrate_account(conn, row)

    def upsert_subaccounts(self, account_id: int, subaccount_types: list[str]) -> None:
        """Ensure the given subaccount types exist for an account."""

        if not subaccount_types:
            return

        with closing(self._connect()) as conn:
            for subaccount_type in subaccount_types:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO subaccounts (account_id, type, display_name)
                    VALUES (?, ?, NULL)
                    """,
                    (account_id, subaccount_type),
                )
            conn.commit()

    def _hydrate_account(self, conn: sqlite3.Connection, row: sqlite3.Row) -> Account:
        identifiers = conn.execute(
            """
            SELECT identifier_value
            FROM account_identifiers
            WHERE account_id = ? AND identifier_type = 'bank_account_number'
            ORDER BY id
            """,
            (row["id"],),
        ).fetchall()
        subaccount_rows = conn.execute(
            """
            SELECT type, display_name
            FROM subaccounts
            WHERE account_id = ?
            ORDER BY type
            """,
            (row["id"],),
        ).fetchall()

        return Account(
            id=row["id"],
            bank=row["bank"],
            bank_account_numbers=[item["identifier_value"] for item in identifiers],
            display_name=row["display_name"],
            iban=row["iban"],
            holder=row["holder"],
            notes=row["notes"],
            balance_cents=row["balance_cents"],
            balance_date=date.fromisoformat(row["balance_date"]) if row["balance_date"] else None,
            subaccounts={
                item["type"]: Subaccount(type=item["type"], display_name=item["display_name"])
                for item in subaccount_rows
            },
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            hidden=bool(row["hidden"]),
        )
