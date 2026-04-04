"""Apply log entries to the SQLite projection."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from penny.vault.log import LogEntry
from penny.vault.manifests import (
    IngestManifest,
    AccountCreatedManifest,
    load_manifest,
)

if TYPE_CHECKING:
    from penny.transactions import Transaction


@dataclass
class IngestResult:
    """Result of applying an ingest entry."""

    account_id: int
    account_bank: str
    account_label: str
    is_new_account: bool
    parser_name: str
    transactions_new: int
    transactions_duplicate: int
    transactions_total: int
    sections: dict[str, int]


def apply_ingest(entry: LogEntry) -> IngestResult:
    """Apply an ingest log entry to the SQLite projection.

    Reads the CSV files from the entry directory, parses them,
    reconciles the account, and stores transactions.
    """
    from penny.accounts.registry import AccountRegistry
    from penny.accounts.storage import AccountStorage
    from penny.db import init_schema
    from penny.ingest import match_file
    from penny.ingest.formats.utils import read_file_with_encoding
    from penny.transactions import store_transactions

    manifest: IngestManifest = entry.read_manifest()  # type: ignore

    if manifest.type != "ingest":
        raise ValueError(f"Expected ingest manifest, got {manifest.type}")

    # Initialize DB schema
    init_schema()

    # Process each CSV file in the entry
    all_transactions: list[Transaction] = []
    parser_name = manifest.parser
    account = None

    for csv_filename in manifest.csv_files:
        csv_path = entry.path / csv_filename
        content = read_file_with_encoding(csv_path)

        # Get parser (use stored parser type from manifest)
        parser = match_file(csv_filename, content, csv_type=manifest.parser)
        parser_name = parser.name

        # Detect and reconcile account
        detection = parser.detect(csv_filename, content)
        registry = AccountRegistry(AccountStorage())
        account = registry.reconcile(detection)

        # Parse transactions
        transactions = parser.parse(csv_filename, content, account_id=account.id)
        all_transactions.extend(transactions)

    if account is None:
        raise ValueError("No CSV files in ingest entry")

    # Store transactions
    new_count, duplicate_count = store_transactions(
        all_transactions,
        source_file=manifest.csv_files[0] if manifest.csv_files else "unknown",
    )

    # Build section counts
    section_counts = Counter(tx.subaccount_type for tx in all_transactions)

    return IngestResult(
        account_id=account.id,
        account_bank=account.bank,
        account_label=account.display_name or f"{account.bank} #{account.id}",
        is_new_account=account.created_at == account.updated_at,
        parser_name=parser_name,
        transactions_new=new_count,
        transactions_duplicate=duplicate_count,
        transactions_total=len(all_transactions),
        sections=dict(section_counts),
    )


def apply_entry(entry: LogEntry) -> None:
    """Apply any log entry to the projection.

    Dispatches to the appropriate handler based on manifest type.
    """
    manifest = entry.read_manifest()

    match manifest.type:
        case "init":
            pass  # Nothing to apply
        case "ingest":
            apply_ingest(entry)
        case "account_created":
            _apply_account_created(entry, manifest)  # type: ignore
        case "account_updated":
            pass  # TODO
        case "account_hidden":
            pass  # TODO
        case "balance_snapshot":
            pass  # TODO
        case "rules":
            pass  # TODO
        case _:
            raise ValueError(f"Unknown manifest type: {manifest.type}")


def _apply_account_created(entry: LogEntry, manifest: AccountCreatedManifest) -> None:
    """Apply account_created entry."""
    from penny.accounts.registry import AccountRegistry
    from penny.accounts.storage import AccountStorage

    registry = AccountRegistry(AccountStorage())
    registry.add(
        bank=manifest.bank,
        bank_account_number=manifest.bank_account_number,
        display_name=manifest.display_name,
        iban=manifest.iban,
    )
