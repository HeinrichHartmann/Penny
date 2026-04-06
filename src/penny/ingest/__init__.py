"""CSV ingestion - bank detection and format parsing."""

from penny.ingest.base import BalanceSnapshot, BankModule, CsvSource, DetectionResult
from penny.ingest.detection import (
    DetectionError,
    get_banks,
    get_supported_csv_types,
    match_file,
    match_source,
    read_file_with_encoding,
)

__all__ = [
    "BalanceSnapshot",
    "BankModule",
    "CsvSource",
    "DetectionError",
    "DetectionResult",
    "get_banks",
    "get_supported_csv_types",
    "match_file",
    "match_source",
    "read_file_with_encoding",
]
