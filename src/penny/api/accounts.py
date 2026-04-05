"""Accounts API router."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from penny.accounts import (
    Account,
    soft_delete_account,
    update_account_balance,
    update_account_metadata,
)
from penny.accounts import (
    get_account as get_account_by_id,
)
from penny.accounts import (
    list_accounts as list_all_accounts,
)
from penny.api.helpers import get_db

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class BalanceSnapshotRequest(BaseModel):
    """Request body for recording a balance snapshot."""

    balance_cents: int
    balance_date: str  # ISO date format
    subaccount_type: str = "giro"
    note: str | None = None


def _account_to_dict(account: Account, transaction_count: int = 0) -> dict:
    """Convert Account model to JSON-serializable dict."""
    return {
        "id": account.id,
        "bank": account.bank,
        "display_name": account.display_name,
        "iban": account.iban,
        "holder": account.holder,
        "notes": account.notes,
        "balance_cents": account.balance_cents,
        "balance_date": account.balance_date.isoformat() if account.balance_date else None,
        "subaccounts": list(account.subaccounts.keys()),
        "transaction_count": transaction_count,
        "label": account.display_name or f"{account.bank} #{account.id}",
        "hidden": account.hidden,
    }


@router.get("")
async def list_accounts(include_hidden: bool = Query(False)):
    """List all bank accounts."""
    accounts = list_all_accounts(include_hidden=include_hidden)

    # Get transaction counts per account
    conn = get_db()
    cursor = conn.cursor()
    counts = {
        row[0]: row[1]
        for row in cursor.execute(
            "SELECT account_id, COUNT(*) FROM transactions GROUP BY account_id"
        ).fetchall()
    }
    conn.close()

    return {
        "accounts": [_account_to_dict(account, counts.get(account.id, 0)) for account in accounts]
    }


@router.get("/{account_id}")
async def get_account(account_id: int):
    """Get a single account by ID."""
    account = get_account_by_id(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Get transaction count
    conn = get_db()
    cursor = conn.cursor()
    count = cursor.execute(
        "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
    ).fetchone()[0]
    conn.close()

    return _account_to_dict(account, count)


@router.patch("/{account_id}")
async def update_account(
    account_id: int,
    display_name: str | None = None,
    iban: str | None = None,
    holder: str | None = None,
    notes: str | None = None,
):
    """Update account metadata."""
    account = get_account_by_id(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    changes = {}
    if display_name is not None:
        changes["display_name"] = display_name
    if iban is not None:
        changes["iban"] = iban
    if holder is not None:
        changes["holder"] = holder
    if notes is not None:
        changes["notes"] = notes

    if changes:
        updated = update_account_metadata(account_id, **changes)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Return updated account
    return await get_account(account_id)


@router.delete("/{account_id}")
async def delete_account(account_id: int):
    """Soft-delete an account (hide it)."""
    if not soft_delete_account(account_id):
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    return {"status": "deleted", "account_id": account_id}


@router.post("/{account_id}/balance")
async def record_balance_snapshot(account_id: int, request: BalanceSnapshotRequest):
    """Record a balance snapshot for an account."""
    account = get_account_by_id(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Parse and validate date
    try:
        snapshot_date = date.fromisoformat(request.balance_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}") from e

    # Update the account balance
    updated = update_account_balance(
        account_id,
        balance_cents=request.balance_cents,
        balance_date=snapshot_date,
    )

    if updated is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Return updated account
    return await get_account(account_id)
