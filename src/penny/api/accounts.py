"""Accounts API router."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from penny.accounts import (
    Account,
    count_balance_anchors_by_account,
    soft_delete_account,
    update_account_metadata,
    upsert_balance_anchor,
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
    """Return balance anchor counts per account from balance_anchors table."""
    return count_balance_anchors_by_account()


def _get_latest_balance_anchor(account_id: int) -> dict | None:
    """Get the latest balance anchor for an account."""
    from penny.sql import get_latest_balance_anchor_sql

    conn = get_db()
    row = conn.execute(get_latest_balance_anchor_sql(), (account_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "balance_cents": row["balance_cents"],
        "anchor_date": row["anchor_date"],
    }


def _get_last_transaction_date(account_id: int) -> str | None:
    """Get the date of the most recent transaction for an account."""
    conn = get_db()
    row = conn.execute(
        "SELECT MAX(date) FROM transactions WHERE account_id = ?", (account_id,)
    ).fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def _account_to_dict(
    account: Account,
    transaction_count: int = 0,
    balance_snapshot_count: int = 0,
    latest_balance: dict | None = None,
    last_transaction_date: str | None = None,
) -> dict:
    """Convert Account model to JSON-serializable dict."""
    return {
        "id": account.id,
        "bank": account.bank,
        "display_name": account.display_name,
        "iban": account.iban,
        "holder": account.holder,
        "notes": account.notes,
        "balance_cents": latest_balance["balance_cents"] if latest_balance else None,
        "balance_date": latest_balance["anchor_date"] if latest_balance else None,
        "balance_snapshot_count": balance_snapshot_count,
        "subaccounts": list(account.subaccounts.keys()),
        "transaction_count": transaction_count,
        "last_transaction_date": last_transaction_date,
        "label": account.display_name or f"{account.bank} #{account.id}",
        "hidden": account.hidden,
    }


@router.get("")
async def list_accounts(include_hidden: bool = Query(False)):
    """List all bank accounts."""
    accounts = list_all_accounts(include_hidden=include_hidden)
    balance_snapshot_counts = _load_balance_snapshot_counts()

    # Get transaction counts and last transaction dates per account
    conn = get_db()
    cursor = conn.cursor()
    tx_stats = {
        row[0]: {"count": row[1], "last_date": row[2]}
        for row in cursor.execute(
            "SELECT account_id, COUNT(*), MAX(date) FROM transactions GROUP BY account_id"
        ).fetchall()
    }
    conn.close()

    result = []
    for account in accounts:
        stats = tx_stats.get(account.id, {"count": 0, "last_date": None})
        latest_balance = _get_latest_balance_anchor(account.id)
        result.append(
            _account_to_dict(
                account,
                transaction_count=stats["count"],
                balance_snapshot_count=balance_snapshot_counts.get(account.id, 0),
                latest_balance=latest_balance,
                last_transaction_date=stats["last_date"],
            )
        )

    return {"accounts": result}


@router.get("/{account_id}")
async def get_account(account_id: int):
    """Get a single account by ID."""
    account = get_account_by_id(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Get transaction count and last date
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT COUNT(*), MAX(date) FROM transactions WHERE account_id = ?", (account_id,)
    ).fetchone()
    conn.close()
    tx_count = row[0] if row else 0
    last_tx_date = row[1] if row else None

    balance_snapshot_counts = _load_balance_snapshot_counts()
    latest_balance = _get_latest_balance_anchor(account_id)

    return _account_to_dict(
        account,
        transaction_count=tx_count,
        balance_snapshot_count=balance_snapshot_counts.get(account_id, 0),
        latest_balance=latest_balance,
        last_transaction_date=last_tx_date,
    )


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

    # Store in balance_anchors table
    upsert_balance_anchor(
        account_id,
        anchor_date=snapshot_date,
        balance_cents=request.balance_cents,
        note=request.note,
        source="manual",
        ledger_sequence=sequence,
    )

    # Return updated account
    return await get_account(account_id)
