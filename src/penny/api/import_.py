"""Import API router."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from penny.ingest import DetectionError
from penny.vault import ingest_csv, IngestRequest

router = APIRouter(prefix="/api", tags=["import"])


@router.post("/import")
async def import_csv(file: UploadFile = File(...)):
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
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Import failed: {e}",
        )

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
            {"type": section, "count": count}
            for section, count in sorted(result.sections.items())
        ],
        "transactions": {
            "new": result.transactions_new,
            "duplicates": result.transactions_duplicate,
            "total_parsed": result.transactions_total,
        },
    }
