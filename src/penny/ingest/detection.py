"""Bank detection and file matching."""

from __future__ import annotations

from pathlib import Path

from penny.ingest.base import BankModule
from penny.ingest.banks import get_banks
from penny.ingest.formats.utils import read_file_with_encoding as _read_file


class DetectionError(ValueError):
    """Raised when a file cannot be detected cleanly."""


def read_file_with_encoding(path: Path) -> str:
    """Read a file with encoding detection."""
    return _read_file(path)


def get_supported_csv_types() -> list[str]:
    """Return the supported bank identifiers."""
    return [bank.bank for bank in get_banks()]


def get_bank_by_type(csv_type: str) -> BankModule:
    """Return a bank module by its identifier."""
    normalized = csv_type.lower()
    for bank in get_banks():
        if bank.bank == normalized:
            return bank

    supported = ", ".join(get_supported_csv_types())
    raise DetectionError(f"Unsupported csv type: {csv_type}. Supported types: {supported}")


def _validate_bank_match(bank: BankModule, filename: str, content: str) -> BankModule:
    """Validate that the bank can handle this file."""
    if bank.match(filename, content):
        return bank

    content_signature_matches = getattr(bank, "content_signature_matches", None)
    if callable(content_signature_matches) and content_signature_matches(content):
        if not bank.filename_pattern.match(filename):
            expected = getattr(bank, "expected_filename_hint", bank.filename_pattern.pattern)
            raise DetectionError(
                "Filename does not match expected export format. "
                f"Expected: {expected}"
            )

    raise DetectionError(f"File does not match selected parser: {bank.bank}")


def match_file(filename: str, content: str, csv_type: str | None = None) -> BankModule:
    """Return the bank module for a file or raise a detection error."""
    if csv_type:
        return _validate_bank_match(get_bank_by_type(csv_type), filename, content)

    banks = get_banks()

    # Try exact match (filename + content)
    for bank in banks:
        if bank.match(filename, content):
            return bank

    # Try content-only match and suggest filename fix
    for bank in banks:
        content_signature_matches = getattr(bank, "content_signature_matches", None)
        if callable(content_signature_matches) and content_signature_matches(content):
            if not bank.filename_pattern.match(filename):
                expected = getattr(bank, "expected_filename_hint", bank.filename_pattern.pattern)
                raise DetectionError(
                    "Filename does not match expected export format. "
                    f"Expected: {expected}"
                )

    raise DetectionError(f"Unknown file format: {filename}")
