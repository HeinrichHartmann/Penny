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
            classification_rule=row["classification_rule"]
            if "classification_rule" in keys
            else None,
            group_id=row["group_id"] if "group_id" in keys else None,
            account_name=row["account_name"] if "account_name" in keys else None,
            account_number=row["account_number"] if "account_number" in keys else None,
            entry_count=row["entry_count"] if "entry_count" in keys else 1,
        )


@dataclass(frozen=True)
class TransactionFilter:
    """Reusable filters for listing transactions."""

    from_date: date | None = None
    to_date: date | None = None
    account_ids: frozenset[int] | None = None
    category_prefix: str | None = None
    search_query: str | None = None
    tab: str | None = None


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
    """Store transactions via the vault write surface."""
    from penny.vault import store_transactions as vault_store_transactions

    return vault_store_transactions(transactions, source_file=source_file)


def _store_transactions_direct(
    conn: sqlite3.Connection,
    transactions: list[Transaction],
    *,
    source_file: str | None = None,
    imported_at: str | None = None,
) -> tuple[int, int]:
    """Store transactions directly in the projection database."""
    imported_at = imported_at or datetime.now().isoformat()
    new_count = 0
    duplicate_count = 0

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
                    None,
                    imported_at,
                    source_file,
                    tx.group_id or tx.fingerprint,
                ),
            )
            new_count += 1
        except sqlite3.IntegrityError:
            duplicate_count += 1

    return new_count, duplicate_count


def _merge_filters(
    filters: TransactionFilter | None,
    account_id: int | None,
) -> TransactionFilter | None:
    """Merge legacy account_id filter into the reusable filter object."""
    if filters is None and account_id is None:
        return None

    account_ids = set(filters.account_ids) if filters and filters.account_ids is not None else None
    if account_id is not None:
        if account_ids is None:
            account_ids = {account_id}
        else:
            account_ids.add(account_id)

    return TransactionFilter(
        from_date=filters.from_date if filters else None,
        to_date=filters.to_date if filters else None,
        account_ids=frozenset(account_ids) if account_ids is not None else None,
        category_prefix=filters.category_prefix if filters else None,
        search_query=filters.search_query if filters else None,
        tab=filters.tab if filters else None,
    )


def filter_transactions(
    transactions: list[Transaction],
    filters: TransactionFilter,
) -> list[Transaction]:
    """Apply reusable filters to a list of transactions."""
    filtered: list[Transaction] = []
    search_query = filters.search_query.lower() if filters.search_query else None

    for transaction in transactions:
        if filters.from_date and transaction.date < filters.from_date:
            continue
        if filters.to_date and transaction.date > filters.to_date:
            continue
        if filters.account_ids is not None and transaction.account_id not in filters.account_ids:
            continue
        if filters.category_prefix:
            if not transaction.category or not transaction.category.startswith(
                filters.category_prefix
            ):
                continue
        if search_query:
            search_text = f"{transaction.raw_buchungstext} {transaction.payee}".lower()
            if search_query not in search_text:
                continue
        if filters.tab == "expense" and transaction.amount_cents >= 0:
            continue
        if filters.tab == "income" and transaction.amount_cents <= 0:
            continue
        filtered.append(transaction)

    return filtered


def list_transactions(
    *,
    filters: TransactionFilter | None = None,
    account_id: int | None = None,
    limit: int | None = 20,
    neutralize: bool = True,
) -> list[Transaction]:
    """List transactions, optionally consolidating transfer groups."""
    merged_filters = _merge_filters(filters, account_id)
    query_account_id = None
    query_limit = limit

    if merged_filters is not None:
        query_limit = None
        if merged_filters.account_ids is not None and len(merged_filters.account_ids) == 1:
            query_account_id = next(iter(merged_filters.account_ids))
    else:
        query_account_id = account_id

    sql, params = list_transactions_query(
        account_id=query_account_id,
        limit=query_limit,
        neutralize=neutralize,
    )

    with closing(connect()) as conn:
        rows = conn.execute(sql, params).fetchall()

    transactions = [Transaction.from_row(row) for row in rows]

    if merged_filters is not None:
        transactions = filter_transactions(transactions, merged_filters)
        if limit is not None:
            transactions = transactions[:limit]

    return transactions


def count_transactions(*, account_id: int | None = None) -> int:
    """Return the number of stored transactions."""
    sql, params = count_transactions_sql(account_id=account_id)

    with closing(connect()) as conn:
        return int(conn.execute(sql, params).fetchone()[0])


def apply_classifications(decisions: list[ClassificationDecision]) -> tuple[int, int]:
    """Persist a full-set classification pass via the vault write surface."""
    from penny.vault import apply_classifications as vault_apply_classifications

    return vault_apply_classifications(decisions)


def _apply_classifications_direct(
    conn: sqlite3.Connection,
    decisions: list[ClassificationDecision],
    *,
    classified_at: str | None = None,
) -> tuple[int, int]:
    """Apply a full-set classification pass directly to the projection."""
    decision_map = {d.fingerprint: d for d in decisions}
    classified_at = classified_at or datetime.now().isoformat()

    conn.execute(clear_classifications_sql())

    for fingerprint, decision in decision_map.items():
        conn.execute(
            update_classification_sql(),
            (decision.category, decision.rule_name, classified_at, fingerprint),
        )

    uncategorized = int(conn.execute(count_uncategorized_sql()).fetchone()[0])
    if uncategorized:
        raise RuntimeError(
            f"Classification pass left {uncategorized} transactions without a category"
        )

    total = int(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])
    return len(decision_map), total - len(decision_map)


def apply_groups(groups: dict[str, str]) -> tuple[int, int]:
    """Assign group_id to transactions via the vault write surface."""
    from penny.vault import apply_groups as vault_apply_groups

    return vault_apply_groups(groups)


def _apply_groups_direct(
    conn: sqlite3.Connection,
    groups: dict[str, str],
) -> tuple[int, int]:
    """Apply transfer groups directly to the projection."""
    conn.execute(reset_groups_sql())

    for fingerprint, group_id in groups.items():
        conn.execute(update_group_sql(), (group_id, fingerprint))

    grouped = int(conn.execute(count_grouped_sql()).fetchone()[0])
    standalone = int(conn.execute(count_standalone_sql()).fetchone()[0])
    return grouped, standalone
