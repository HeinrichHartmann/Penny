"""Ingest service - write CSV imports to vault and apply."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from penny.vault.apply import IngestResult, apply_ingest
from penny.vault.config import VaultConfig
from penny.vault.ledger import Ledger, LedgerEntry

if TYPE_CHECKING:
    pass


# App version - should come from package metadata
APP_VERSION = "0.2.0"


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
    from penny.ingest import DetectionError, match_file

    if config is None:
        config = VaultConfig()

    # Ensure vault is initialized
    if not config.is_initialized():
        config.initialize()

    ledger = Ledger(config.path)

    # Decode content if bytes
    if isinstance(request.content, bytes):
        try:
            content_str = request.content.decode("utf-8")
        except UnicodeDecodeError:
            content_str = request.content.decode("cp1252")
        content_bytes = request.content
    else:
        content_str = request.content
        content_bytes = request.content.encode("utf-8")

    # Detect parser first (fail fast if unknown format)
    try:
        parser = match_file(request.filename, content_str, csv_type=request.csv_type)
    except DetectionError:
        raise

    # Get sequence and timestamp
    sequence = ledger.next_sequence()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create transaction directory
    tx_dir = config.path / "transactions" / f"{sequence:04d}_{timestamp}"
    tx_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV file
    csv_path = tx_dir / request.filename
    csv_path.write_bytes(content_bytes)

    # Create ledger entry (record contains all manifest data)
    entry = LedgerEntry(
        sequence=sequence,
        entry_type="ingest",
        enabled=True,
        timestamp=timestamp,
        record={
            "csv_files": [request.filename],
            "parser": parser.bank,
            "parser_version": f"{parser.bank}@1",
            "app_version": APP_VERSION,
        },
    )

    # Append to history.tsv
    ledger.append_entry(entry)

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
    from penny.ingest import match_file

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
        # Decode if needed
        if isinstance(content, bytes):
            try:
                content_str = content.decode("utf-8")
            except UnicodeDecodeError:
                content_str = content.decode("cp1252")
            content_bytes = content
        else:
            content_str = content
            content_bytes = content.encode("utf-8")

        # Detect parser (all files should match same parser)
        file_parser = match_file(filename, content_str)
        if parser is None:
            parser = file_parser
        elif parser.bank != file_parser.bank:
            raise ValueError(f"Mixed file formats: {parser.bank} vs {file_parser.bank}")

        content_dict[filename] = content_bytes
        filenames.append(filename)

    if parser is None:
        raise ValueError("No files to ingest")

    # Get sequence and timestamp
    sequence = ledger.next_sequence()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create transaction directory
    tx_dir = config.path / "transactions" / f"{sequence:04d}_{timestamp}"
    tx_dir.mkdir(parents=True, exist_ok=True)

    # Write CSV files
    for filename, content_bytes in content_dict.items():
        csv_path = tx_dir / filename
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

    # Apply the entry
    result = apply_ingest(entry, config)

    return result
