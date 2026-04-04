"""SQLite-backed account storage."""

from __future__ import annotations

from contextlib import closing
from datetime import date, datetime

from penny.accounts.models import Account, Subaccount
from penny.config import default_data_dir, default_db_path
from penny.db import connect

# Re-export for backwards compatibility
__all__ = ["AccountStorage", "default_data_dir", "default_db_path"]


class AccountStorage:
    """Persistence layer for accounts.

    Uses the centralized database connection from db.py.
    """

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
        with closing(connect()) as conn:
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
        with closing(connect()) as conn:
            query = "SELECT id FROM accounts"
            params: list[object] = []
            if not include_hidden:
                query += " WHERE hidden = 0"
            query += " ORDER BY id"
            ids = [row["id"] for row in conn.execute(query, params).fetchall()]
        return [account for account_id in ids if (account := self.get_account(account_id, include_hidden=True))]

    def get_account(self, account_id: int, *, include_hidden: bool = True) -> Account | None:
        """Return an account by ID."""
        with closing(connect()) as conn:
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
        with closing(connect()) as conn:
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
        with closing(connect()) as conn:
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

        with closing(connect()) as conn:
            for subaccount_type in subaccount_types:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO subaccounts (account_id, type, display_name)
                    VALUES (?, ?, NULL)
                    """,
                    (account_id, subaccount_type),
                )
            conn.commit()

    def _hydrate_account(self, conn, row) -> Account:
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
