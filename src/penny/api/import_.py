"""Import API router."""

from collections import Counter

from fastapi import APIRouter, File, HTTPException, UploadFile

from penny.accounts import reconcile_account
from penny.db import init_default_db
from penny.ingest import DetectionError, match_file
from penny.transactions import store_transactions

router = APIRouter(prefix="/api", tags=["import"])


@router.post("/import")
async def import_csv(file: UploadFile = File(...)):
    """Import transactions from a CSV file.

    This endpoint mirrors the CLI `penny import` command:
    1. Detect the bank format from filename and content
    2. Reconcile or create the bank account
    3. Parse transactions
    4. Store with deduplication
    """
    # Read file content
    content_bytes = await file.read()

    # Try UTF-8 first, fall back to CP1252 (common for German bank CSVs)
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("cp1252")

    filename = file.filename or "upload.csv"

    # Detect parser
    try:
        parser = match_file(filename, content)
    except DetectionError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect CSV format: {e}",
        )

    # Detect account info
    detection = parser.detect(filename, content)

    # Reconcile account (find existing or create new)
    try:
        account = reconcile_account(detection)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Account reconciliation failed: {e}",
        )

    # Parse transactions
    parsed_transactions = parser.parse(filename, content, account_id=account.id)

    # Store transactions with deduplication
    init_default_db()
    new_count, duplicate_count = store_transactions(
        parsed_transactions,
        source_file=filename,
    )

    # Build section summary
    section_counts = Counter(tx.subaccount_type for tx in parsed_transactions)

    return {
        "status": "success",
        "filename": filename,
        "parser": detection.parser_name,
        "account": {
            "id": account.id,
            "bank": account.bank,
            "display_name": account.display_name,
            "label": account.display_name or f"{account.bank} #{account.id}",
            "is_new": account.created_at == account.updated_at,  # New if timestamps match
        },
        "sections": [
            {"type": section, "count": count}
            for section, count in sorted(section_counts.items())
        ],
        "transactions": {
            "new": new_count,
            "duplicates": duplicate_count,
            "total_parsed": len(parsed_transactions),
        },
    }
