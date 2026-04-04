"""SQLite-backed transaction storage."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from penny.sql import (
    clear_classifications_sql,
    count_grouped_sql,
    count_standalone_sql,
    count_transactions_sql,
    count_uncategorized_sql,
    insert_transaction_sql,
    list_transactions_query,
    reset_groups_sql,
    update_classification_sql,
    update_group_sql,
)
from penny.db import connect, init_schema, set_db_path
from penny.transactions.models import Transaction

if TYPE_CHECKING:
    from penny.classify import ClassificationDecision


def generate_fingerprint(
    account_id: int,
    tx_date: date,
    amount_cents: int,
    payee: str,
    reference: str | None,
) -> str:
    """Generate a stable transaction fingerprint."""
    if reference:
        key = f"{account_id}:{reference}"
    else:
        key = f"{account_id}:{tx_date.isoformat()}:{amount_cents}:{payee[:50]}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class TransactionStorage:
    """Persistence layer for parsed transactions."""

    def __init__(self, db_path: Path | None = None):
        # Always set db_path (even None resets to default)
        set_db_path(Path(db_path) if db_path is not None else None)
        init_schema()

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

        with closing(connect()) as conn:
            for tx in transactions:
                try:
                    conn.execute(
                        insert_transaction_sql(),
                        (
                            tx.fingerprint,
                            tx.account_id,
                            tx.subaccount_type,
                            tx.date.isoformat(),
                            tx.payee,
                            tx.memo,
                            tx.amount_cents,
                            tx.value_date.isoformat() if tx.value_date else None,
                            tx.transaction_type,
                            tx.reference,
                            tx.raw_buchungstext,
                            json.dumps(tx.raw_row, ensure_ascii=False, sort_keys=True),
                            tx.category,
                            tx.classification_rule,
                            None,  # classified_at
                            imported_at,
                            source_file,
                            tx.fingerprint,  # group_id defaults to fingerprint
                        ),
                    )
                    new_count += 1
                except sqlite3.IntegrityError:
                    duplicate_count += 1
            conn.commit()

        return new_count, duplicate_count

    def list_transactions(
        self,
        *,
        account_id: int | None = None,
        limit: int | None = 20,
        neutralize: bool = True,
    ) -> list[Transaction]:
        """List transactions, optionally consolidating transfer groups."""
        sql, params = list_transactions_query(
            account_id=account_id,
            limit=limit,
            neutralize=neutralize,
        )

        with closing(connect()) as conn:
            rows = conn.execute(sql, params).fetchall()

        return [Transaction.from_row(row) for row in rows]

    def count_transactions(self, *, account_id: int | None = None) -> int:
        """Return the number of stored transactions."""
        sql, params = count_transactions_sql(account_id=account_id)

        with closing(connect()) as conn:
            return int(conn.execute(sql, params).fetchone()[0])

    def apply_classifications(self, decisions: list[ClassificationDecision]) -> tuple[int, int]:
        """Persist a full-set classification pass."""
        decision_map = {d.fingerprint: d for d in decisions}
        classified_at = datetime.now().isoformat()

        with closing(connect()) as conn:
            # Clear all existing classifications
            conn.execute(clear_classifications_sql())

            # Apply new classifications
            for fingerprint, decision in decision_map.items():
                conn.execute(
                    update_classification_sql(),
                    (decision.category, decision.rule_name, classified_at, fingerprint),
                )

            # Verify all transactions have a category
            uncategorized = int(conn.execute(count_uncategorized_sql()).fetchone()[0])
            if uncategorized:
                conn.rollback()
                raise RuntimeError(
                    f"Classification pass left {uncategorized} transactions without a category"
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
        """
        with closing(connect()) as conn:
            # Reset all to standalone
            conn.execute(reset_groups_sql())

            # Apply grouped assignments
            for fingerprint, group_id in groups.items():
                conn.execute(update_group_sql(), (group_id, fingerprint))

            conn.commit()

            # Count results
            grouped = int(conn.execute(count_grouped_sql()).fetchone()[0])
            standalone = int(conn.execute(count_standalone_sql()).fetchone()[0])

        return grouped, standalone
