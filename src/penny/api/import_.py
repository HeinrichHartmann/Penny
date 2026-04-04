"""Import API router."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from penny.ingest import DetectionError
from penny.vault import IngestRequest, ingest_csv
from penny.vault.config import VaultConfig
from penny.vault.log import LogManager
from penny.vault.manifests import IngestManifest

router = APIRouter(prefix="/api", tags=["import"])


def _auto_run_classification() -> None:
    """Run classification rules automatically after import.

    This is called after transactions are stored to immediately classify them.
    Silently skips if no rules file exists or if classification fails.
    """
    try:
        from penny.classify import load_rules_config, run_classification_pass
        from penny.transactions import apply_classifications, list_transactions
        from penny.vault import ensure_rules_snapshot

        # Get the rules snapshot path (returns None if no rules exist)
        rules_path = ensure_rules_snapshot()
        if not rules_path or not rules_path.exists():
            return

        # Load rules configuration
        config = load_rules_config(rules_path)

        # Get all transactions
        transactions = list_transactions(limit=None, neutralize=False)
        if not transactions:
            return

        # Run classification pass
        result = run_classification_pass(transactions, config)

        # Apply classifications
        apply_classifications(result.decisions)
    except Exception:
        # Silently skip if classification fails - don't break import flow
        pass


@router.post("/import")
async def import_csv(file: Annotated[UploadFile, File()]):
    """Import transactions from a CSV file.

    Flow (via vault):
    1. Write CSV to vault log entry
    2. Apply entry: detect parser, reconcile account, parse, store
    3. Return result
    """
    content_bytes = await file.read()
    filename = file.filename or "upload.csv"

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

    # Auto-run classification rules after import (Issue #8)
    _auto_run_classification()

    return {
        "status": "success",
        "filename": filename,
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


@router.get("/imports")
async def list_imports():
    """List all past imports with metadata from vault manifests.

    Returns:
        List of import records with timestamp, filename, parser, and transaction counts.
    """
    config = VaultConfig()
    log = LogManager(config)

    imports = []
    for entry in log.iter_entries():
        try:
            manifest = entry.read_manifest()
        except Exception:
            # Skip entries with invalid manifests
            continue

        # Only include ingest entries
        if not isinstance(manifest, IngestManifest):
            continue

        # Get account info if available
        # We need to look up the account from the transactions table
        # since the manifest doesn't store account_id
        account_label = None
        account_id = None

        # Try to get account info from the database based on the parser/bank
        # This is a heuristic - the actual account is determined during apply
        try:
            from penny.api.helpers import get_db

            conn = get_db()
            cursor = conn.cursor()
            # Find the most likely account based on the bank name from parser
            row = cursor.execute(
                """
                SELECT a.id, a.display_name, a.bank
                FROM accounts a
                WHERE a.bank = ?
                ORDER BY a.id DESC
                LIMIT 1
                """,
                (manifest.parser,),
            ).fetchone()
            conn.close()

            if row:
                account_id = row[0]
                account_label = row[1] or f"{row[2]} #{row[0]}"
        except Exception:
            pass

        imports.append(
            {
                "sequence": entry.sequence,
                "timestamp": manifest.timestamp,
                "filenames": manifest.csv_files,
                "parser": manifest.parser,
                "status": manifest.status,
                "account_id": account_id,
                "account_label": account_label,
            }
        )

    # Return in reverse chronological order (most recent first)
    return {"imports": list(reversed(imports))}
