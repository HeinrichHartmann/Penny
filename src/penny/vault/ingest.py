"""Ingest service - write CSV imports to vault log and apply."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from penny.vault.apply import IngestResult, apply_ingest
from penny.vault.config import VaultConfig
from penny.vault.log import LogManager
from penny.vault.manifests import IngestManifest

if TYPE_CHECKING:
    pass


# App version - should come from package metadata
APP_VERSION = "0.1.0"


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
    """Ingest a CSV file through the vault log.

    Flow:
    1. Detect parser from filename/content
    2. Create log entry directory with CSV file
    3. Write manifest
    4. Apply entry (parse, store transactions)
    5. Return result

    Args:
        request: The ingest request with filename and content
        config: Optional vault config (uses default if not provided)

    Returns:
        IngestResult with account and transaction details
    """
    from penny.ingest import DetectionError, match_file

    if config is None:
        config = VaultConfig()

    log = LogManager(config)

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

    # Create manifest
    manifest = IngestManifest(
        csv_files=[request.filename],
        parser=parser.bank,
        parser_version=f"{parser.bank}@1",  # TODO: get from parser
        app_version=APP_VERSION,
        status="applied",
    )

    # Write to vault log
    # We need to write the content to a temp file first, then copy
    entry = log.append_with_content(
        entry_type=f"ingest_{parser.bank}",
        manifest=manifest,
        content={request.filename: content_bytes},
    )

    # Apply the entry (parse and store)
    result = apply_ingest(entry)

    return result


def ingest_csv_files(
    files: list[tuple[str, str | bytes]],
    config: VaultConfig | None = None,
) -> IngestResult:
    """Ingest multiple CSV files as a single log entry.

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

    log = LogManager(config)

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

    # Create manifest
    manifest = IngestManifest(
        csv_files=filenames,
        parser=parser.bank,
        parser_version=f"{parser.bank}@1",
        app_version=APP_VERSION,
        status="applied",
    )

    # Write to vault log
    entry = log.append_with_content(
        entry_type=f"ingest_{parser.bank}",
        manifest=manifest,
        content=content_dict,
    )

    # Apply the entry
    result = apply_ingest(entry)

    return result
