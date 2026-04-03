"""Transaction models."""

from __future__ import annotations

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
