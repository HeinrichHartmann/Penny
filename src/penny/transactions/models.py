"""Transaction models."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date


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
