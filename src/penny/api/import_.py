"""Import API router."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from penny.ingest import DetectionError
from penny.runtime_rules import run_stored_rules
from penny.vault import IngestRequest, ingest_csv
from penny.vault.config import VaultConfig
from penny.vault.ledger import Ledger, LedgerEntry

router = APIRouter(prefix="/api", tags=["import"])


def _auto_run_classification() -> None:
    """Run classification rules automatically after import.

    This is called after transactions are stored to immediately classify them.
    """
    run_stored_rules(ensure_rules=True, include_hidden=True)


@router.post("/import")
async def import_file(file: Annotated[UploadFile, File()]):
    """Import data from file (CSV, rules.py, or balance-anchors.tsv).

    Detects file type and routes appropriately:
    - .csv -> Import transactions
    - .py -> Update classification rules
    - .tsv -> Import balance snapshots
    """
    filename = file.filename or "upload"
    content_bytes = await file.read()

    # Route based on file extension
    if filename.endswith(".py"):
        # Import rules file
        return await _import_rules(filename, content_bytes)
    elif filename.endswith(".tsv"):
        # Import balance snapshots
        return await _import_balance_anchors(filename, content_bytes)
    else:
        # Import CSV (transactions)
        return await _import_csv(filename, content_bytes)


async def _import_csv(filename: str, content_bytes: bytes):
    """Import transactions from CSV file."""
    request = IngestRequest(
        filename=filename,
        content=content_bytes,
    )

    try:
        result = ingest_csv(request)
    except DetectionError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect CSV format: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Import failed: {e}",
        ) from e

    try:
        _auto_run_classification()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Import stored transactions, but rules evaluation failed: {e}",
        ) from e

    return {
        "status": "success",
        "filename": filename,
        "type": "csv",
        "parser": result.parser_name,
        "account": {
            "id": result.account_id,
            "bank": result.account_bank,
            "label": result.account_label,
            "is_new": result.is_new_account,
        },
        "sections": [
            {"type": section, "count": count} for section, count in sorted(result.sections.items())
        ],
        "transactions": {
            "new": result.transactions_new,
            "duplicates": result.transactions_duplicate,
            "total_parsed": result.transactions_total,
        },
    }


async def _import_rules(filename: str, content_bytes: bytes):
    """Import classification rules from .py file."""
    from penny.vault.rules import update_rules_and_apply

    content = content_bytes.decode("utf-8")

    try:
        path = update_rules_and_apply(content)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Rules import failed: {e}",
        ) from e

    return {
        "status": "success",
        "filename": filename,
        "type": "rules",
        "path": path,
    }


async def _import_balance_anchors(filename: str, content_bytes: bytes):
    """Import balance snapshots from TSV file.

    TSV format:
        account_iban    date    balance_cents    note
        DE89...         2024-01-15    100000    Monthly snapshot
    """
    import csv
    from datetime import UTC, datetime

    from penny.accounts import update_account_balance
    from penny.api.helpers import get_db

    config = VaultConfig()
    if not config.is_initialized():
        config.initialize()

    ledger = Ledger(config.path)

    content = content_bytes.decode("utf-8")
    reader = csv.DictReader(content.splitlines(), delimiter="\t")

    # Generate single timestamp for all snapshots in this batch
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sequence = ledger.next_sequence()

    snapshots_created = 0
    snapshots_skipped = 0
    errors = []
    balance_records = []

    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
        try:
            # Extract fields
            account_iban = row.get("account_iban", "").strip()
            date_str = row.get("date", "").strip()
            balance_cents_str = row.get("balance_cents", "").strip()
            note = row.get("note", "").strip()

            if not account_iban or not date_str or not balance_cents_str:
                errors.append(f"Row {row_num}: Missing required fields")
                snapshots_skipped += 1
                continue

            # Find account by IBAN
            conn = get_db()
            cursor = conn.cursor()
            acc_row = cursor.execute(
                "SELECT id FROM accounts WHERE iban = ? LIMIT 1",
                (account_iban,),
            ).fetchone()
            conn.close()

            if not acc_row:
                errors.append(f"Row {row_num}: Account not found for IBAN {account_iban}")
                snapshots_skipped += 1
                continue

            account_id = acc_row[0]
            balance_cents = int(balance_cents_str)

            # Apply the balance update
            from datetime import date as date_type

            snapshot_date = date_type.fromisoformat(date_str)
            update_account_balance(account_id, balance_cents=balance_cents, balance_date=snapshot_date)

            balance_records.append({
                "account_id": account_id,
                "account_iban": account_iban,
                "snapshot_date": date_str,
                "balance_cents": balance_cents,
                "note": note,
            })
            snapshots_created += 1

        except ValueError as e:
            errors.append(f"Row {row_num}: Invalid number format - {e}")
            snapshots_skipped += 1
        except Exception as e:
            errors.append(f"Row {row_num}: {e}")
            snapshots_skipped += 1

    # Create single ledger entry for the batch
    if balance_records:
        entry = LedgerEntry(
            sequence=sequence,
            entry_type="balance",
            enabled=True,
            timestamp=timestamp,
            record={
                "filename": filename,
                "snapshots": balance_records,
            },
        )
        ledger.append_entry(entry)

    return {
        "status": "success",
        "filename": filename,
        "type": "balance_anchors",
        "snapshots_created": snapshots_created,
        "snapshots_skipped": snapshots_skipped,
        "errors": errors if errors else None,
    }


@router.get("/demo-files")
async def list_demo_files():
    """List available demo files for download.

    Returns metadata about demo files that can be imported.
    """
    from pathlib import Path

    from penny.demo_bootstrap import get_demo_csv_path

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    demo_csv_path = get_demo_csv_path()
    rules_path = fixtures_dir / "demo_rules.py"
    balance_anchors_path = fixtures_dir / "balance-anchors.tsv"

    files = []

    if demo_csv_path.exists():
        files.append({
            "filename": demo_csv_path.name,
            "type": "csv",
            "size": demo_csv_path.stat().st_size,
        })

    if rules_path.exists():
        files.append({
            "filename": rules_path.name,
            "type": "rules",
            "size": rules_path.stat().st_size,
        })

    if balance_anchors_path.exists():
        files.append({
            "filename": balance_anchors_path.name,
            "type": "balance_anchors",
            "size": balance_anchors_path.stat().st_size,
        })

    return {"files": files}


@router.get("/demo-files/{filename}")
async def download_demo_file(filename: str):
    """Download a specific demo file.

    Returns the raw file content for client-side upload.
    """
    from pathlib import Path

    from fastapi.responses import Response

    from penny.demo_bootstrap import get_demo_csv_path

    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    demo_csv_path = get_demo_csv_path()

    # Map filename to path
    file_map = {
        demo_csv_path.name: demo_csv_path,
        "demo_rules.py": fixtures_dir / "demo_rules.py",
        "balance-anchors.tsv": fixtures_dir / "balance-anchors.tsv",
    }

    file_path = file_map.get(filename)
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Demo file not found: {filename}")

    content = file_path.read_bytes()

    # Determine content type
    if filename.endswith(".csv"):
        media_type = "text/csv"
    elif filename.endswith(".py"):
        media_type = "text/x-python"
    elif filename.endswith(".tsv"):
        media_type = "text/tab-separated-values"
    else:
        media_type = "application/octet-stream"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/imports")
async def list_imports():
    """List all past imports with metadata from ledger.

    Returns:
        List of import records including CSV imports, rules updates, and balance snapshots.
    """
    config = VaultConfig()
    if not config.is_initialized():
        return {"imports": []}

    ledger = Ledger(config.path)
    imports = []

    for entry in ledger.read_entries():
        # Handle rules entries
        if entry.entry_type == "rules":
            imports.append({
                "sequence": entry.sequence,
                "timestamp": entry.timestamp,
                "filenames": [entry.record.get("filename", "rules.py")],
                "parser": "rules",
                "status": "applied",
                "account_id": None,
                "account_label": None,
                "enabled": entry.enabled,
                "warning": None,
                "type": "rules",
            })
            continue

        # Handle balance entries
        if entry.entry_type == "balance":
            snapshots = entry.record.get("snapshots", [])
            account_ids = set(s["account_id"] for s in snapshots)
            imports.append({
                "sequence": entry.sequence,
                "timestamp": entry.timestamp,
                "filenames": [entry.record.get("filename", "balance-anchors.tsv")],
                "parser": "balance_anchors",
                "status": "applied",
                "account_id": None,
                "account_label": f"{len(snapshots)} snapshot(s) for {len(account_ids)} account(s)",
                "enabled": entry.enabled,
                "warning": None,
                "type": "balance_anchors",
            })
            continue

        # Handle ingest entries
        if entry.entry_type == "ingest":
            parser = entry.record.get("parser", "unknown")
            csv_files = entry.record.get("csv_files", [])

            # Get account info if available
            account_label = None
            account_id = None

            try:
                from penny.api.helpers import get_db

                conn = get_db()
                cursor = conn.cursor()
                row = cursor.execute(
                    """
                    SELECT a.id, a.display_name, a.bank
                    FROM accounts a
                    WHERE a.bank = ?
                    ORDER BY a.id DESC
                    LIMIT 1
                    """,
                    (parser,),
                ).fetchone()
                conn.close()

                if row:
                    account_id = row[0]
                    account_label = row[1] or f"{row[2]} #{row[0]}"
            except Exception:
                pass

            imports.append({
                "sequence": entry.sequence,
                "timestamp": entry.timestamp,
                "filenames": csv_files,
                "parser": parser,
                "status": "applied",
                "account_id": account_id,
                "account_label": account_label,
                "enabled": entry.enabled,
                "warning": None,
                "type": "ingest",
            })

    # Return in reverse chronological order (most recent first)
    return {"imports": list(reversed(imports))}


@router.post("/imports/{sequence}/toggle")
async def toggle_import_enabled(sequence: int):
    """Toggle the enabled state of an import entry.

    This modifies the enabled flag in history.tsv.
    Changes take effect on next DB rebuild.
    """
    config = VaultConfig()
    if not config.is_initialized():
        raise HTTPException(status_code=404, detail="Vault not initialized")

    ledger = Ledger(config.path)

    # Find the entry
    entry = ledger.get_entry(sequence)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Import entry {sequence} not found")

    # Only allow toggling ingest entries
    if entry.entry_type != "ingest":
        raise HTTPException(status_code=400, detail="Only ingest entries can be toggled")

    # Toggle enabled state
    new_enabled = not entry.enabled

    # Update in ledger (atomic write)
    ledger.update_enabled(sequence, new_enabled)

    return {"sequence": sequence, "enabled": new_enabled}


@router.post("/rebuild")
async def rebuild_database():
    """Rebuild the database from vault log.

    Clears the existing database and replays all enabled log entries.
    Also runs classification rules after rebuild.
    """
    from penny.vault.replay import replay_vault

    config = VaultConfig()
    result = replay_vault(config)

    # Run classification rules after rebuild
    _auto_run_classification()

    return {
        "status": "success",
        "entries_processed": result.entries_processed,
        "entries_by_type": result.entries_by_type,
    }
