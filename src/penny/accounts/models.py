"""Account models."""

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Subaccount:
    """A subaccount within a bank account."""

    type: str
    display_name: str | None = None


@dataclass
class Account:
    """An account tracked by Penny."""

    id: int
    bank: str
    bank_account_numbers: list[str] = field(default_factory=list)
    display_name: str | None = None
    iban: str | None = None
    holder: str | None = None
    notes: str | None = None
    balance_cents: int | None = None
    balance_date: date | None = None
    subaccounts: dict[str, Subaccount] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    hidden: bool = False
