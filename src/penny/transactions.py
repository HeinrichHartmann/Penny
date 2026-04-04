"""Transaction domain: models and business logic."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from penny.db import connect
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

if TYPE_CHECKING:
    from penny.classify import ClassificationDecision


# =============================================================================
# MODELS
# =============================================================================


@dataclass
class Transaction:
    """Parsed transaction ready for storage."""

    fingerprint: str
    account_id: int
    subaccount_type: str
    date: date
    payee: str
    memo: str
    amount_cents: int
    value_date: date | None
    transaction_type: str
    reference: str | None
    raw_buchungstext: str
    raw_row: dict
    category: str | None = None
    classification_rule: str | None = None
    group_id: str | None = None
    # Resolved at load time (not stored in DB)
    account_name: str | None = None
    account_number: str | None = None
    entry_count: int = 1  # Number of entries in this group (1 for standalone)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Transaction:
        """Hydrate a Transaction from a database row."""
        keys = row.keys()
        return cls(
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
            classification_rule=row["classification_rule"] if "classification_rule" in keys else None,
            group_id=row["group_id"] if "group_id" in keys else None,
            account_name=row["account_name"] if "account_name" in keys else None,
            account_number=row["account_number"] if "account_number" in keys else None,
            entry_count=row["entry_count"] if "entry_count" in keys else 1,
        )


# =============================================================================
# FUNCTIONS
# =============================================================================


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


def store_transactions(
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


def count_transactions(*, account_id: int | None = None) -> int:
    """Return the number of stored transactions."""
    sql, params = count_transactions_sql(account_id=account_id)

    with closing(connect()) as conn:
        return int(conn.execute(sql, params).fetchone()[0])


def apply_classifications(decisions: list[ClassificationDecision]) -> tuple[int, int]:
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


def apply_groups(groups: dict[str, str]) -> tuple[int, int]:
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
