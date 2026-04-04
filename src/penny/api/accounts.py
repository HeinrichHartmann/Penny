"""Accounts API router."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from penny.accounts import Account, get_account as get_account_by_id, list_accounts as list_all_accounts, soft_delete_account
from penny.api.helpers import get_db

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


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
        "accounts": [
            _account_to_dict(account, counts.get(account.id, 0)) for account in accounts
        ]
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
    display_name: Optional[str] = None,
    iban: Optional[str] = None,
    holder: Optional[str] = None,
    notes: Optional[str] = None,
):
    """Update account metadata."""
    account = get_account_by_id(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Update via direct SQL (AccountStorage doesn't have update method yet)
    conn = get_db()
    cursor = conn.cursor()

    updates = []
    params = []
    if display_name is not None:
        updates.append("display_name = ?")
        params.append(display_name)
    if iban is not None:
        updates.append("iban = ?")
        params.append(iban)
    if holder is not None:
        updates.append("holder = ?")
        params.append(holder)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(account_id)

        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()

    conn.close()

    # Return updated account
    return await get_account(account_id)


@router.delete("/{account_id}")
async def delete_account(account_id: int):
    """Soft-delete an account (hide it)."""
    if not soft_delete_account(account_id):
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    return {"status": "deleted", "account_id": account_id}
