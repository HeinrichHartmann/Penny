"""Accounts API router."""

from datetime import UTC, date, datetime

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
from penny.vault.config import VaultConfig
from penny.vault.ledger import Ledger, LedgerEntry

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class BalanceSnapshotRequest(BaseModel):
    """Request body for recording a balance snapshot."""

    balance_cents: int
    balance_date: str  # ISO date format
    subaccount_type: str = "giro"
    note: str | None = None


def _load_balance_snapshot_counts() -> dict[int, int]:
    """Return enabled balance snapshot counts per account from the vault ledger."""
    config = VaultConfig()
    if not config.is_initialized():
        return {}

    counts: dict[int, int] = {}
    for entry in Ledger(config.path).read_entries():
        if entry.entry_type != "balance" or not entry.enabled:
            continue
        for snapshot in entry.record.get("snapshots", []):
            account_id = snapshot.get("account_id")
            if account_id is None:
                continue
            counts[account_id] = counts.get(account_id, 0) + 1
    return counts


def _account_to_dict(
    account: Account,
    transaction_count: int = 0,
    balance_snapshot_count: int = 0,
) -> dict:
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
        "balance_snapshot_count": balance_snapshot_count,
        "subaccounts": list(account.subaccounts.keys()),
        "transaction_count": transaction_count,
        "label": account.display_name or f"{account.bank} #{account.id}",
        "hidden": account.hidden,
    }


@router.get("")
async def list_accounts(include_hidden: bool = Query(False)):
    """List all bank accounts."""
    accounts = list_all_accounts(include_hidden=include_hidden)
    balance_snapshot_counts = _load_balance_snapshot_counts()

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
            _account_to_dict(
                account,
                counts.get(account.id, 0),
                balance_snapshot_counts.get(account.id, 0),
            )
            for account in accounts
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

    balance_snapshot_counts = _load_balance_snapshot_counts()
    return _account_to_dict(account, count, balance_snapshot_counts.get(account_id, 0))


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
    """Record a balance snapshot for an account.

    Writes to the vault ledger (source of truth), appends to balances.tsv,
    and updates the SQLite accounts table (cached balance for display).
    """
    from penny.vault.balance_file import BalanceRow, append_balance_row, format_account_key

    account = get_account_by_id(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Parse and validate date
    try:
        snapshot_date = date.fromisoformat(request.balance_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}") from e

    # Write to vault ledger (source of truth)
    config = VaultConfig()
    if not config.is_initialized():
        config.initialize()

    # Build account key for balances.tsv
    account_number = account.bank_account_numbers[0] if account.bank_account_numbers else ""
    account_key = format_account_key(account.bank, account_number)

    ledger = Ledger(config.path)
    sequence = ledger.next_sequence()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    balance_record = {
        "account_id": account_id,
        "account_key": account_key,  # bank/number format for matching
        "snapshot_date": request.balance_date,
        "balance_cents": request.balance_cents,
        "note": request.note or "",
    }

    entry = LedgerEntry(
        sequence=sequence,
        entry_type="balance",
        enabled=True,
        timestamp=timestamp,
        record={
            "filename": f"ui_snapshot_{account_id}_{request.balance_date}",
            "snapshots": [balance_record],
        },
    )
    ledger.append_entry(entry)

    # Append to balances.tsv (human-readable, importable)
    append_balance_row(
        BalanceRow(
            account=account_key,
            date=snapshot_date,
            balance_cents=request.balance_cents,
            note=request.note or "",
        ),
        config,
    )

    # Also update SQLite accounts table (cached balance for quick display)
    update_account_balance(
        account_id,
        balance_cents=request.balance_cents,
        balance_date=snapshot_date,
    )

    # Return updated account
    return await get_account(account_id)
