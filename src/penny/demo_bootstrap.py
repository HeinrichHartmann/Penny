"""Bootstrap demo data on first vault initialization."""

from __future__ import annotations

from pathlib import Path

from penny.vault.config import VaultConfig
from penny.vault.ingest import IngestRequest, ingest_csv


def get_demo_csv_path() -> Path:
    """Return the path to the bundled demo CSV file."""
    return Path(__file__).parent / "fixtures" / "20260404-12345678-umsatz-camt52v8.CSV"


def should_load_demo_data(config: VaultConfig | None = None) -> bool:
    """Check if demo data should be loaded.

    Demo data is loaded only on first initialization when the vault is completely empty
    (no imports and no mutations exist yet).

    Args:
        config: Optional vault config

    Returns:
        True if demo data should be loaded
    """
    if config is None:
        config = VaultConfig()

    # Check if transactions directory exists
    if not config.transactions_dir.exists():
        return False

    # Check if transactions directory is empty
    tx_entries = list(config.transactions_dir.iterdir())
    if len(tx_entries) > 0:
        return False

    # Check if there are any mutations in the mutation log
    if not config.mutations_path.exists():
        return False

    # Read mutation log and check if there are any data rows (beyond header)
    lines = config.mutations_path.read_text(encoding="utf-8").strip().split("\n")
    # If only header exists (1 line) or empty, vault is empty
    return len(lines) <= 1


def bootstrap_demo_data(config: VaultConfig | None = None) -> bool:
    """Load demo data into a new vault.

    Args:
        config: Optional vault config

    Returns:
        True if demo data was loaded, False if skipped
    """
    if config is None:
        config = VaultConfig()

    # Only load if vault is empty
    if not should_load_demo_data(config):
        return False

    demo_csv_path = get_demo_csv_path()

    if not demo_csv_path.exists():
        # Demo data file not found, skip silently
        return False

    # Read demo CSV content
    demo_content = demo_csv_path.read_bytes()

    # Create ingest request
    request = IngestRequest(
        filename=demo_csv_path.name,
        content=demo_content,
        csv_type="sparkasse",
    )

    # Import demo data
    result = ingest_csv(request, config=config)

    # Set demo account display name
    from penny.accounts import update_account_metadata

    update_account_metadata(result.account_id, display_name="Demo Account")

    # Add balance snapshots to demonstrate anchor-based projection
    _add_demo_balance_snapshots(config, result.account_id)

    return True


def _add_demo_balance_snapshots(config: VaultConfig, account_id: int) -> None:
    """Add demo balance snapshots with intentional deviations.

    These snapshots demonstrate:
    1. Balance anchor backward/forward projection
    2. Inconsistency detection when projections don't match actual snapshots

    Demo data spans: April 2022 - March 2024 (~2 years)
    """
    from datetime import UTC, datetime

    from penny.vault.ledger import Ledger, LedgerEntry

    ledger = Ledger(config.path)
    sequence = ledger.next_sequence()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Define balance snapshots with strategic deviations
    # Note: These are intentionally offset to create inconsistencies
    # demonstrating the anchor-based projection and delta detection
    snapshots = [
        # October 2022 - 6 months in (accurate baseline)
        {
            "date": "2022-10-15",
            "balance_cents": 280000,  # €2,800
            "note": "Q4 2022 baseline",
        },
        # April 2023 - 1 year in (OFF BY +€250)
        {
            "date": "2023-04-15",
            "balance_cents": 305000,  # €3,050 (missing €250 in transactions)
            "note": "Mid-year - missing transactions",
        },
        # October 2023 - 18 months in (OFF BY -€180)
        {
            "date": "2023-10-15",
            "balance_cents": 296000,  # €2,960 (€180 extra spending not recorded)
            "note": "Fall - unrecorded spending",
        },
        # February 2024 - near end (OFF BY +€320)
        {
            "date": "2024-02-01",
            "balance_cents": 338000,  # €3,380 (missing €320 in expenses)
            "note": "Winter - data gap",
        },
        # March 2024 - final anchor (OFF BY -€200, projects forward)
        {
            "date": "2024-03-29",
            "balance_cents": 310000,  # €3,100 (€200 missing income)
            "note": "Final - missing income",
        },
    ]

    balance_records = []
    for snapshot in snapshots:
        balance_records.append({
            "account_id": account_id,
            "account_iban": None,
            "snapshot_date": snapshot["date"],
            "balance_cents": snapshot["balance_cents"],
            "note": snapshot["note"],
        })

    entry = LedgerEntry(
        sequence=sequence,
        entry_type="balance",
        enabled=True,
        timestamp=timestamp,
        record={
            "filename": "demo_snapshots",
            "snapshots": balance_records,
        },
    )
    ledger.append_entry(entry)
