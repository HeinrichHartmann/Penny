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

    # Check if any imports exist
    if not config.imports_dir.exists():
        return False

    # Check if imports directory is empty
    import_entries = list(config.imports_dir.iterdir())
    if len(import_entries) > 0:
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
    ingest_csv(request, config=config)

    return True
