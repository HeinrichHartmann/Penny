"""Balance file operations - append-only balances.tsv for import/export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from penny.vault.config import VaultConfig
from penny.vault.ledger import Ledger

BALANCE_FILE_HEADER = "account\tdate\tbalance_cents\tnote\n"


@dataclass
class BalanceRow:
    """A row in balances.tsv."""

    account: str  # bank/account_number format, e.g. "comdirect/9788862492"
    date: date
    balance_cents: int
    note: str

    def to_tsv_line(self) -> str:
        """Convert to TSV line."""
        return f"{self.account}\t{self.date.isoformat()}\t{self.balance_cents}\t{self.note}"

    @classmethod
    def from_tsv_line(cls, line: str) -> BalanceRow:
        """Parse from TSV line."""
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3:
            raise ValueError(f"Invalid balance line (expected at least 3 columns): {line}")

        account = parts[0]
        date_str = parts[1]
        balance_cents = int(parts[2])
        note = parts[3] if len(parts) > 3 else ""

        return cls(
            account=account,
            date=date.fromisoformat(date_str),
            balance_cents=balance_cents,
            note=note,
        )


def balance_file_path(config: VaultConfig) -> Path:
    """Return path to balances.tsv (in vault root)."""
    return config.path / "balances.tsv"


def append_balance_row(row: BalanceRow, config: VaultConfig | None = None) -> None:
    """Append a balance row to balances.tsv."""
    if config is None:
        config = VaultConfig()

    path = balance_file_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Create file with header if it doesn't exist
    if not path.exists():
        path.write_text(BALANCE_FILE_HEADER, encoding="utf-8")

    # Append row
    with path.open("a", encoding="utf-8") as f:
        f.write(row.to_tsv_line() + "\n")


def read_balance_rows(config: VaultConfig | None = None) -> list[BalanceRow]:
    """Read all rows from balances.tsv."""
    if config is None:
        config = VaultConfig()

    path = balance_file_path(config)
    if not path.exists():
        return []

    rows: list[BalanceRow] = []
    with path.open("r", encoding="utf-8") as f:
        header = f.readline()
        if not header.startswith("account\t"):
            raise ValueError(f"Invalid balance file header: {header}")

        for line_num, line in enumerate(f, start=2):
            if not line.strip():
                continue
            try:
                rows.append(BalanceRow.from_tsv_line(line))
            except Exception as e:
                raise ValueError(f"Failed to parse line {line_num}: {e}") from e

    return rows


def get_existing_balance_keys(config: VaultConfig) -> set[tuple[str, str]]:
    """Get set of (account, date) pairs from existing balance entries in ledger."""
    ledger = Ledger(config.path)
    keys: set[tuple[str, str]] = set()

    for entry in ledger.read_entries():
        if entry.entry_type != "balance":
            continue
        for snapshot in entry.record.get("snapshots", []):
            # Build account key from snapshot
            account_key = _snapshot_to_account_key(snapshot)
            if account_key:
                keys.add((account_key, snapshot["snapshot_date"]))

    return keys


def _snapshot_to_account_key(snapshot: dict) -> str | None:
    """Convert a snapshot record to account key (bank/number format)."""
    # New snapshots have account_key directly
    if "account_key" in snapshot:
        return snapshot["account_key"]
    return None


def format_account_key(bank: str, account_number: str) -> str:
    """Format bank and account number as account key."""
    return f"{bank}/{account_number}"


def parse_account_key(account: str) -> tuple[str, str]:
    """Parse account key into (bank, account_number)."""
    if "/" not in account:
        raise ValueError(f"Invalid account format (expected bank/number): {account}")
    bank, number = account.split("/", 1)
    return bank, number


@dataclass
class BalanceImportResult:
    """Result of importing balances."""

    imported: int
    skipped: int  # duplicates
    errors: list[str]


def import_balances(
    content: str | bytes,
    config: VaultConfig | None = None,
) -> BalanceImportResult:
    """Import balances from TSV content.

    Deduplicates by (account, date) - skips rows that already exist in ledger.
    Creates ledger entries for new balances.
    """
    from datetime import UTC, datetime

    from penny.accounts import find_account_by_bank_account_number
    from penny.vault.ledger import LedgerEntry

    if config is None:
        config = VaultConfig()

    if isinstance(content, bytes):
        content = content.decode("utf-8")

    # Parse rows from content
    lines = content.strip().split("\n")
    if not lines:
        return BalanceImportResult(imported=0, skipped=0, errors=["Empty file"])

    # Check header
    header = lines[0]
    if not header.startswith("account\t"):
        return BalanceImportResult(imported=0, skipped=0, errors=[f"Invalid header: {header}"])

    rows: list[BalanceRow] = []
    errors: list[str] = []
    for line_num, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        try:
            rows.append(BalanceRow.from_tsv_line(line))
        except Exception as e:
            errors.append(f"Line {line_num}: {e}")

    if not rows:
        return BalanceImportResult(imported=0, skipped=0, errors=errors or ["No data rows"])

    # Get existing balance keys for deduplication
    existing_keys = get_existing_balance_keys(config)

    # Group new rows by their key, keeping latest value per (account, date)
    new_balances: dict[tuple[str, str], BalanceRow] = {}
    skipped = 0
    for row in rows:
        key = (row.account, row.date.isoformat())
        if key in existing_keys:
            skipped += 1
            continue
        new_balances[key] = row  # Later rows overwrite earlier ones

    if not new_balances:
        return BalanceImportResult(imported=0, skipped=skipped, errors=errors)

    # Create ledger entries for new balances
    ledger = Ledger(config.path)
    imported = 0

    for row in new_balances.values():
        # Parse account key to find account
        try:
            bank, account_number = parse_account_key(row.account)
        except ValueError as e:
            errors.append(f"{row.account}: {e}")
            continue

        account = find_account_by_bank_account_number(bank, account_number, include_hidden=True)
        if account is None:
            # Auto-create account for balance-only imports
            from penny.accounts import create_account

            account = create_account(
                bank=bank,
                bank_account_numbers=[account_number],
            )

        # Create ledger entry
        sequence = ledger.next_sequence()
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        entry = LedgerEntry(
            sequence=sequence,
            entry_type="balance",
            enabled=True,
            timestamp=timestamp,
            record={
                "filename": f"import_{row.account}_{row.date.isoformat()}",
                "snapshots": [
                    {
                        "account_id": account.id,
                        "account_key": row.account,
                        "snapshot_date": row.date.isoformat(),
                        "balance_cents": row.balance_cents,
                        "note": row.note,
                    }
                ],
            },
        )
        ledger.append_entry(entry)

        # Apply balance to balance_anchors table
        from penny.accounts import upsert_balance_anchor

        upsert_balance_anchor(
            account.id,
            anchor_date=row.date,
            balance_cents=row.balance_cents,
            note=row.note,
            source="tsv_import",
            ledger_sequence=sequence,
        )

        # Also append to balances.tsv
        append_balance_row(row, config)

        imported += 1

    return BalanceImportResult(imported=imported, skipped=skipped, errors=errors)
