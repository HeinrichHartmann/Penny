"""CSV ingestion - bank detection and format parsing."""

from penny.ingest.base import BalanceSnapshot, BankModule, DetectionResult
from penny.ingest.detection import (
    DetectionError,
    get_banks,
    get_supported_csv_types,
    match_file,
    read_file_with_encoding,
)

__all__ = [
    "BalanceSnapshot",
    "BankModule",
    "DetectionError",
    "DetectionResult",
    "get_banks",
    "get_supported_csv_types",
    "match_file",
    "read_file_with_encoding",
]
