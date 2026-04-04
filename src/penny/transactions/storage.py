"""SQLite-backed transaction storage."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from penny.accounts.storage import default_db_path
from penny.transactions.models import Transaction

if TYPE_CHECKING:
    from penny.classify import ClassificationDecision


def generate_fingerprint(
    account_id: int,
    date: date,
    amount_cents: int,
    payee: str,
    reference: str | None,
) -> str:
    """Generate a stable transaction fingerprint."""

    if reference:
        key = f"{account_id}:{reference}"
    else:
        key = f"{account_id}:{date.isoformat()}:{amount_cents}:{payee[:50]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class TransactionStorage:
    """Persistence layer for parsed transactions."""

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
                    source_file TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
                CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
                CREATE INDEX IF NOT EXISTS idx_transactions_payee ON transactions(payee);
                """
            )
            self._ensure_column(conn, "transactions", "category", "TEXT")
            self._ensure_column(conn, "transactions", "classification_rule", "TEXT")
            self._ensure_column(conn, "transactions", "classified_at", "TEXT")
            self._ensure_column(conn, "transactions", "group_id", "TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_transactions_group ON transactions(group_id)"
            )
            conn.commit()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def store_transactions(
        self,
        transactions: list[Transaction],
        *,
        source_file: str | None = None,
    ) -> tuple[int, int]:
        """Store transactions and return counts for new and duplicate rows."""

        imported_at = datetime.now().isoformat()
        new_count = 0
        duplicate_count = 0

        with closing(self._connect()) as conn:
            for transaction in transactions:
                try:
                    conn.execute(
                        """
                        INSERT INTO transactions (
                            fingerprint, account_id, subaccount_type, date, payee, memo,
                            amount_cents, value_date, transaction_type, reference,
                            raw_buchungstext, raw_row, category, classification_rule,
                            classified_at, imported_at, source_file
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            transaction.fingerprint,
                            transaction.account_id,
                            transaction.subaccount_type,
                            transaction.date.isoformat(),
                            transaction.payee,
                            transaction.memo,
                            transaction.amount_cents,
                            transaction.value_date.isoformat() if transaction.value_date else None,
                            transaction.transaction_type,
                            transaction.reference,
                            transaction.raw_buchungstext,
                            json.dumps(transaction.raw_row, ensure_ascii=False, sort_keys=True),
                            transaction.category,
                            transaction.classification_rule,
                            None,
                            imported_at,
                            source_file,
                        ),
                    )
                    new_count += 1
                except sqlite3.IntegrityError:
                    duplicate_count += 1
            conn.commit()

        return new_count, duplicate_count

    def list_transactions(self, *, account_id: int | None = None, limit: int | None = 20) -> list[Transaction]:
        """List recent transactions with resolved account info."""

        with closing(self._connect()) as conn:
            # Join with accounts to get account_name, and with account_identifiers for account_number
            query = """
                SELECT t.fingerprint, t.account_id, t.subaccount_type, t.date, t.payee, t.memo,
                       t.amount_cents, t.value_date, t.transaction_type, t.reference,
                       t.raw_buchungstext, t.raw_row, t.category, t.classification_rule,
                       t.group_id,
                       COALESCE(a.display_name, a.bank || ' #' || a.id) as account_name,
                       ai.identifier_value as account_number
                FROM transactions t
                LEFT JOIN accounts a ON t.account_id = a.id
                LEFT JOIN account_identifiers ai ON t.account_id = ai.account_id
                    AND ai.identifier_type = 'bank_account_number'
            """
            params: list[object] = []
            if account_id is not None:
                query += " WHERE t.account_id = ?"
                params.append(account_id)
            query += " ORDER BY t.date DESC, t.fingerprint DESC"
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(query, params).fetchall()

        return [self._hydrate_transaction(row) for row in rows]

    def count_transactions(self, *, account_id: int | None = None) -> int:
        """Return the number of stored transactions."""

        with closing(self._connect()) as conn:
            query = "SELECT COUNT(*) FROM transactions"
            params: list[object] = []
            if account_id is not None:
                query += " WHERE account_id = ?"
                params.append(account_id)
            return int(conn.execute(query, params).fetchone()[0])

    def apply_classifications(self, decisions: list[ClassificationDecision]) -> tuple[int, int]:
        """Persist a full-set classification pass."""

        decision_map = {decision.fingerprint: decision for decision in decisions}
        classified_at = datetime.now().isoformat()

        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE transactions
                SET category = NULL,
                    classification_rule = NULL,
                    classified_at = NULL
                """
            )
            for fingerprint, decision in decision_map.items():
                conn.execute(
                    """
                    UPDATE transactions
                    SET category = ?, classification_rule = ?, classified_at = ?
                    WHERE fingerprint = ?
                    """,
                    (decision.category, decision.rule_name, classified_at, fingerprint),
                )
            conn.commit()

            total = int(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])
        return len(decision_map), total - len(decision_map)

    def apply_groups(self, groups: dict[str, str]) -> tuple[int, int]:
        """Assign group_id to transactions.

        Args:
            groups: Mapping of fingerprint -> group_id

        Returns:
            Tuple of (grouped_count, standalone_count)

        Every transaction gets a group_id:
        - If in `groups` mapping: use the provided group_id
        - Otherwise: use fingerprint as group_id (standalone = own group)
        """
        with closing(self._connect()) as conn:
            # First, set all transactions to their fingerprint (standalone)
            conn.execute("UPDATE transactions SET group_id = fingerprint")

            # Then, apply the grouped assignments
            for fingerprint, group_id in groups.items():
                conn.execute(
                    "UPDATE transactions SET group_id = ? WHERE fingerprint = ?",
                    (group_id, fingerprint),
                )
            conn.commit()

            # Count results
            grouped = conn.execute(
                """
                SELECT COUNT(*) FROM transactions
                WHERE group_id != fingerprint
                """
            ).fetchone()[0]
            standalone = conn.execute(
                """
                SELECT COUNT(*) FROM transactions
                WHERE group_id = fingerprint
                """
            ).fetchone()[0]

        return int(grouped), int(standalone)

    def _hydrate_transaction(self, row: sqlite3.Row) -> Transaction:
        keys = row.keys()
        return Transaction(
            fingerprint=row["fingerprint"],
            account_id=row["account_id"],
            subaccount_type=row["subaccount_type"],
            date=date.fromisoformat(row["date"]),
            payee=row["payee"],
            memo=row["memo"],
            amount_cents=row["amount_cents"],
            value_date=date.fromisoformat(row["value_date"]) if row["value_date"] else None,
            transaction_type=row["transaction_type"] or "",
            reference=row["reference"],
            raw_buchungstext=row["raw_buchungstext"] or "",
            raw_row=json.loads(row["raw_row"]) if row["raw_row"] else {},
            category=row["category"],
            classification_rule=row["classification_rule"],
            group_id=row["group_id"] if "group_id" in keys else None,
            # Resolved fields from JOIN (may not be present in all queries)
            account_name=row["account_name"] if "account_name" in keys else None,
            account_number=row["account_number"] if "account_number" in keys else None,
        )
