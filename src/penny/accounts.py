"""Account domain: models and business logic."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from penny.db import connect
from penny.sql import (
    find_account_by_bank_account_number_sql,
    get_account_identifiers_sql,
    get_account_sql,
    get_subaccounts_sql,
    insert_account_identifier_sql,
    insert_account_sql,
    insert_subaccount_sql,
    list_account_ids_sql,
    soft_delete_account_sql,
    upsert_subaccount_sql,
)

if TYPE_CHECKING:
    from penny.ingest import DetectionResult


# =============================================================================
# EXCEPTIONS
# =============================================================================


class DuplicateAccountError(ValueError):
    """Raised when an account already exists."""


# =============================================================================
# MODELS
# =============================================================================


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


# =============================================================================
# INTERNAL HELPERS
# =============================================================================


def _hydrate_account(conn, row) -> Account:
    """Hydrate an Account from a database row."""
    identifiers = conn.execute(
        get_account_identifiers_sql(),
        (row["id"],),
    ).fetchall()
    subaccount_rows = conn.execute(
        get_subaccounts_sql(),
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


# =============================================================================
# STORAGE FUNCTIONS
# =============================================================================


def create_account(
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
            insert_account_sql(),
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
                insert_account_identifier_sql(),
                (account_id, account_number),
            )

        for subaccount in (subaccounts or {}).values():
            conn.execute(
                insert_subaccount_sql(),
                (account_id, subaccount.type, subaccount.display_name),
            )

        conn.commit()

    account = get_account(account_id, include_hidden=True)
    if account is None:
        raise RuntimeError(f"Account {account_id} was not persisted")
    return account


def list_accounts(*, include_hidden: bool = False) -> list[Account]:
    """Return all accounts."""
    with closing(connect()) as conn:
        ids = [
            row["id"]
            for row in conn.execute(list_account_ids_sql(include_hidden)).fetchall()
        ]
    return [
        account
        for account_id in ids
        if (account := get_account(account_id, include_hidden=True))
    ]


def get_account(account_id: int, *, include_hidden: bool = True) -> Account | None:
    """Return an account by ID."""
    with closing(connect()) as conn:
        row = conn.execute(
            get_account_sql(include_hidden),
            [account_id],
        ).fetchone()
        if row is None:
            return None
        return _hydrate_account(conn, row)


def soft_delete_account(account_id: int) -> bool:
    """Hide an account without removing it."""
    with closing(connect()) as conn:
        cursor = conn.execute(
            soft_delete_account_sql(),
            (datetime.now().isoformat(), account_id),
        )
        conn.commit()
        return cursor.rowcount > 0


def find_account_by_bank_account_number(
    bank: str,
    account_number: str,
    *,
    include_hidden: bool = True,
) -> Account | None:
    """Find an account by bank and bank account number."""
    with closing(connect()) as conn:
        row = conn.execute(
            find_account_by_bank_account_number_sql(include_hidden),
            [bank, account_number],
        ).fetchone()
        if row is None:
            return None
        return _hydrate_account(conn, row)


def upsert_subaccounts(account_id: int, subaccount_types: list[str]) -> None:
    """Ensure the given subaccount types exist for an account."""
    if not subaccount_types:
        return

    with closing(connect()) as conn:
        for subaccount_type in subaccount_types:
            conn.execute(
                upsert_subaccount_sql(),
                (account_id, subaccount_type),
            )
        conn.commit()


# =============================================================================
# BUSINESS LOGIC (formerly AccountRegistry)
# =============================================================================


def add_account(
    bank: str,
    bank_account_number: str | None = None,
    **kwargs,
) -> Account:
    """Create a new account, checking for duplicates."""
    if bank_account_number:
        existing = find_account_by_bank_account_number(
            bank,
            bank_account_number,
            include_hidden=True,
        )
        if existing is not None:
            raise DuplicateAccountError(
                f"Account already exists for {bank} account number {bank_account_number}"
            )

    bank_account_numbers = [bank_account_number] if bank_account_number else []
    return create_account(
        bank=bank,
        bank_account_numbers=bank_account_numbers,
        **kwargs,
    )


def remove_account(account_id: int) -> bool:
    """Soft-delete an account."""
    return soft_delete_account(account_id)


def reconcile_account(detection: DetectionResult) -> Account:
    """Find or create the account for a detected CSV file."""
    if not detection.bank_account_number:
        raise ValueError("Cannot reconcile account without a bank account number")

    account = find_account_by_bank_account_number(
        detection.bank,
        detection.bank_account_number,
        include_hidden=False,
    )
    if account is not None:
        upsert_subaccounts(account.id, detection.detected_subaccounts)
        refreshed = get_account(account.id, include_hidden=True)
        return refreshed if refreshed is not None else account

    subaccounts = {
        subaccount_type: Subaccount(type=subaccount_type)
        for subaccount_type in detection.detected_subaccounts
    }
    return add_account(
        detection.bank,
        bank_account_number=detection.bank_account_number,
        subaccounts=subaccounts,
    )
