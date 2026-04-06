"""Ingest service - write CSV imports to vault and apply."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from penny.db import connect
from penny.sql import check_import_hash_sql, insert_import_hash_sql
from penny.vault.apply import IngestResult, apply_ingest
from penny.vault.config import VaultConfig
from penny.vault.ledger import Ledger, LedgerEntry

if TYPE_CHECKING:
    pass


# App version - should come from package metadata
APP_VERSION = "0.2.0"


class DuplicateImportError(Exception):
    """Raised when attempting to import a CSV that has already been imported."""

    def __init__(self, content_hash: str, existing_sequence: int):
        self.content_hash = content_hash
        self.existing_sequence = existing_sequence
        super().__init__(f"Duplicate CSV: content already imported in entry #{existing_sequence}")


def _compute_content_hash(content: bytes) -> str:
    """Compute SHA256 hash of content."""
    return hashlib.sha256(content).hexdigest()


def _check_duplicate_import(content_hash: str) -> int | None:
    """Check if content hash already exists. Returns existing sequence or None."""
    conn = connect()
    try:
        row = conn.execute(check_import_hash_sql(), (content_hash,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _store_import_hash(content_hash: str, sequence: int) -> None:
    """Store content hash for deduplication."""
    conn = connect()
    try:
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(insert_import_hash_sql(), (content_hash, sequence, timestamp))
        conn.commit()
    finally:
        conn.close()


@dataclass
class IngestRequest:
    """Request to ingest CSV file(s)."""

    filename: str
    content: str | bytes
    csv_type: str | None = None


def ingest_csv(
    request: IngestRequest,
    config: VaultConfig | None = None,
) -> IngestResult:
    """Ingest a CSV file through the vault.

    Flow:
    1. Detect parser from filename/content
    2. Write files to transactions/{seq}_{timestamp}/
    3. Write manifest.json
    4. Append to history.tsv
    5. Apply entry (parse, store transactions)

    Args:
        request: The ingest request with filename and content
        config: Optional vault config

    Returns:
        IngestResult with account and transaction details
    """
    from penny.ingest import CsvSource, DetectionError, match_source

    if config is None:
        config = VaultConfig()

    # Ensure vault is initialized
    if not config.is_initialized():
        config.initialize()

    ledger = Ledger(config.path)

    source = CsvSource.from_content(request.filename, request.content)

    # Check for duplicate import
    content_hash = _compute_content_hash(source.raw_bytes)
    existing_sequence = _check_duplicate_import(content_hash)
    if existing_sequence is not None:
        raise DuplicateImportError(content_hash, existing_sequence)

    # Detect parser first (fail fast if unknown format)
    try:
        parser = match_source(source, csv_type=request.csv_type)
    except DetectionError:
        raise

    # Get sequence and timestamp
    sequence = ledger.next_sequence()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Ensure transactions directory exists
    tx_dir = config.path / "transactions"
    tx_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV file with PI prefix (e.g., PI0001_original.csv)
    prefixed_filename = f"PI{sequence:04d}_{source.filename}"
    csv_path = tx_dir / prefixed_filename
    csv_path.write_bytes(source.raw_bytes)

    # Create ledger entry (record contains all manifest data)
    entry = LedgerEntry(
        sequence=sequence,
        entry_type="ingest",
        enabled=True,
        timestamp=timestamp,
        record={
            "csv_files": [source.filename],
            "parser": parser.bank,
            "parser_version": f"{parser.bank}@1",
            "app_version": APP_VERSION,
        },
    )

    # Append to history.tsv
    ledger.append_entry(entry)

    # Store content hash for deduplication
    _store_import_hash(content_hash, sequence)

    # Apply the entry (parse and store)
    result = apply_ingest(entry, config)

    return result


def ingest_csv_files(
    files: list[tuple[str, str | bytes]],
    config: VaultConfig | None = None,
) -> IngestResult:
    """Ingest multiple CSV files as a single entry.

    Args:
        files: List of (filename, content) tuples
        config: Optional vault config

    Returns:
        IngestResult with combined account and transaction details
    """
    from penny.ingest import CsvSource, match_source

    if not files:
        raise ValueError("No files to ingest")

    if config is None:
        config = VaultConfig()

    # Ensure vault is initialized
    if not config.is_initialized():
        config.initialize()

    ledger = Ledger(config.path)

    # Process all files - they should all be for the same parser/account
    content_dict: dict[str, bytes] = {}
    parser = None
    filenames = []

    for filename, content in files:
        source = CsvSource.from_content(filename, content)

        # Detect parser (all files should match same parser)
        file_parser = match_source(source)
        if parser is None:
            parser = file_parser
        elif parser.bank != file_parser.bank:
            raise ValueError(f"Mixed file formats: {parser.bank} vs {file_parser.bank}")

        content_dict[source.filename] = source.raw_bytes
        filenames.append(source.filename)

    if parser is None:
        raise ValueError("No files to ingest")

    # Check for duplicate import (combined hash of all files)
    combined_content = b"".join(content_dict[f] for f in sorted(content_dict.keys()))
    content_hash = _compute_content_hash(combined_content)
    existing_sequence = _check_duplicate_import(content_hash)
    if existing_sequence is not None:
        raise DuplicateImportError(content_hash, existing_sequence)

    # Get sequence and timestamp
    sequence = ledger.next_sequence()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Ensure transactions directory exists
    tx_dir = config.path / "transactions"
    tx_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV files with PI prefix (e.g., PI0001_original.csv)
    for filename, content_bytes in content_dict.items():
        prefixed_filename = f"PI{sequence:04d}_{filename}"
        csv_path = tx_dir / prefixed_filename
        csv_path.write_bytes(content_bytes)

    # Create ledger entry (record contains all manifest data)
    entry = LedgerEntry(
        sequence=sequence,
        entry_type="ingest",
        enabled=True,
        timestamp=timestamp,
        record={
            "csv_files": filenames,
            "parser": parser.bank,
            "parser_version": f"{parser.bank}@1",
            "app_version": APP_VERSION,
        },
    )

    # Append to history.tsv
    ledger.append_entry(entry)

    # Store content hash for deduplication
    _store_import_hash(content_hash, sequence)

    # Apply the entry
    result = apply_ingest(entry, config)

    return result
