"""Apply log entries to the SQLite projection."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from penny.vault.config import VaultConfig
from penny.vault.ledger import LedgerEntry

if TYPE_CHECKING:
    from penny.ingest.base import BalanceSnapshot
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
    balance_snapshots_stored: int = 0


def apply_ingest(entry: LedgerEntry, config: VaultConfig | None = None) -> IngestResult:
    """Apply an ingest entry to the SQLite projection.

    Reads the CSV files from the entry directory, parses them,
    reconciles the account, and stores transactions.
    """
    from penny.accounts import (
        Subaccount,
        _create_account_direct,
        _find_account_by_bank_account_number_in_conn,
        _get_account_in_conn,
        _upsert_subaccounts_direct,
    )
    from penny.db import init_default_db, transaction
    from penny.ingest import CsvSource, match_source
    from penny.transactions import _store_transactions_direct

    if config is None:
        config = VaultConfig()

    if entry.entry_type != "ingest":
        raise ValueError(f"Expected ingest entry, got {entry.entry_type}")

    # Get manifest data from entry record
    manifest_data = entry.record

    # Initialize DB (idempotent, initializes schema too)
    init_default_db()

    all_transactions: list[Transaction] = []
    all_balance_snapshots: list[tuple[str, BalanceSnapshot]] = []  # (csv_filename, snapshot)
    parser_name = manifest_data["parser"]
    account = None
    csv_files = manifest_data["csv_files"]

    with transaction() as conn:
        for csv_filename in csv_files:
            source = CsvSource.from_path(
                entry.get_csv_path(config.path, csv_filename),
                filename=csv_filename,
            )

            parser = match_source(source, csv_type=manifest_data["parser"])
            parser_name = parser.name

            detection = parser.detect(source)
            if not detection.bank_account_number:
                raise ValueError("Cannot reconcile account without a bank account number")

            account = _find_account_by_bank_account_number_in_conn(
                conn,
                detection.bank,
                detection.bank_account_number,
                include_hidden=False,
            )
            if account is None:
                account = _create_account_direct(
                    conn,
                    bank=detection.bank,
                    bank_account_numbers=[detection.bank_account_number],
                    iban=detection.iban,  # Store IBAN for balance anchor matching
                    subaccounts={
                        subaccount_type: Subaccount(type=subaccount_type)
                        for subaccount_type in detection.detected_subaccounts
                    },
                    created_at=entry.timestamp,
                    updated_at=entry.timestamp,
                )
            else:
                _upsert_subaccounts_direct(conn, account.id, detection.detected_subaccounts)
                refreshed = _get_account_in_conn(conn, account.id, include_hidden=True)
                if refreshed is not None:
                    account = refreshed

            transactions = parser.parse(source, account_id=account.id)
            all_transactions.extend(transactions)

            # Extract balance snapshots from CSV
            balance_snapshots = parser.extract_balances(source)
            for snapshot in balance_snapshots:
                all_balance_snapshots.append((source.filename, snapshot))

        if account is None:
            raise ValueError("No CSV files in ingest entry")

        new_count, duplicate_count = _store_transactions_direct(
            conn,
            all_transactions,
            source_file=csv_files[0] if csv_files else "unknown",
            imported_at=entry.timestamp,
        )

    # Build section counts
    section_counts = Counter(tx.subaccount_type for tx in all_transactions)

    # Store balance snapshots (outside the transaction block to avoid nested DB ops)
    balance_snapshots_stored = 0
    if all_balance_snapshots and account is not None:
        balance_snapshots_stored = _store_balance_snapshots(
            account_id=account.id,
            snapshots=all_balance_snapshots,
            ledger_sequence=entry.sequence,
        )

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
        balance_snapshots_stored=balance_snapshots_stored,
    )


def _store_balance_snapshots(
    account_id: int,
    snapshots: list[tuple[str, BalanceSnapshot]],
    ledger_sequence: int,
) -> int:
    """Store balance snapshots extracted from CSV to balance_anchors table.

    Sums all subaccount balances for the same date into a single account balance.
    Returns number of balance anchors stored (one per unique date).
    """
    from penny.accounts import upsert_balance_anchor

    if not snapshots:
        return 0

    # Group snapshots by date and sum balances across subaccounts
    # (bank exports often have giro + visa + tagesgeld sections)
    date_totals: dict[date, int] = {}
    for _csv_filename, snapshot in snapshots:
        if snapshot.snapshot_date not in date_totals:
            date_totals[snapshot.snapshot_date] = 0
        date_totals[snapshot.snapshot_date] += snapshot.balance_cents

    # Store each date's total balance as an anchor
    stored = 0
    for snapshot_date, total_cents in date_totals.items():
        upsert_balance_anchor(
            account_id,
            anchor_date=snapshot_date,
            balance_cents=total_cents,
            source="csv",
            ledger_sequence=ledger_sequence,
        )
        stored += 1

    return stored


def apply_entry(entry: LedgerEntry, config: VaultConfig) -> None:
    """Apply a ledger entry to the projection.

    Dispatches to the appropriate handler based on entry type.
    """
    match entry.entry_type:
        case "ingest":
            apply_ingest(entry, config)
        case "balance":
            _apply_balance(entry, config)
        case "rules":
            _apply_rules(entry, config)
        case "mutation":
            _apply_mutation_entry(entry, config)
        case _:
            raise ValueError(f"Unknown entry type: {entry.entry_type}")


def _apply_balance(entry: LedgerEntry, config: VaultConfig) -> None:
    """Apply balance entry to balance_anchors table."""
    from penny.accounts import upsert_balance_anchor

    _ = config  # unused but required by interface
    record = entry.record
    # Balance entries have a list of snapshots
    for snapshot in record.get("snapshots", []):
        snapshot_date = date.fromisoformat(snapshot["snapshot_date"])
        upsert_balance_anchor(
            snapshot["account_id"],
            anchor_date=snapshot_date,
            balance_cents=snapshot["balance_cents"],
            note=snapshot.get("note"),
            source="tsv_import",
            ledger_sequence=entry.sequence,
        )


def _apply_rules(entry: LedgerEntry, config: VaultConfig) -> None:
    """Apply rules entry - rules file already exists on disk, nothing to apply."""
    pass


def _apply_mutation_entry(entry: LedgerEntry, config: VaultConfig) -> None:
    """Apply a mutation entry from the ledger."""
    record = entry.record
    mutation_type = record["mutation_type"]
    entity_id = record.get("entity_id", "")
    payload = record.get("payload", {})

    _apply_mutation_data(
        mutation_type=mutation_type,
        entity_id=entity_id,
        payload=payload,
        timestamp=entry.timestamp,
    )


def _apply_mutation_data(
    *,
    mutation_type: str,
    entity_id: str,
    payload: dict,
    timestamp: str,
) -> None:
    """Apply mutation data to the SQLite projection."""
    from penny.accounts import (
        Subaccount,
        _create_account_direct,
        _soft_delete_account_direct,
        _update_account_metadata_direct,
        _upsert_subaccounts_direct,
    )
    from penny.db import transaction
    from penny.transactions import _apply_groups_direct

    with transaction() as conn:
        if mutation_type == "account_created":
            _create_account_direct(
                conn,
                bank=payload["bank"],
                bank_account_numbers=payload.get("bank_account_numbers") or [],
                display_name=payload.get("display_name"),
                iban=payload.get("iban"),
                holder=payload.get("holder"),
                notes=payload.get("notes"),
                subaccounts={
                    item["type"]: Subaccount(
                        type=item["type"], display_name=item.get("display_name")
                    )
                    for item in payload.get("subaccounts", [])
                },
                created_at=timestamp,
                updated_at=timestamp,
            )
            return

        if mutation_type == "account_updated":
            _update_account_metadata_direct(
                conn,
                int(entity_id),
                updated_at=timestamp,
                **payload,
            )
            return

        if mutation_type == "account_hidden":
            _soft_delete_account_direct(conn, int(entity_id), updated_at=timestamp)
            return

        if mutation_type == "subaccounts_upserted":
            _upsert_subaccounts_direct(conn, int(entity_id), payload.get("subaccount_types", []))
            return

        if mutation_type == "transactions_stored":
            from penny.transactions import Transaction, _store_transactions_direct

            transactions = [
                Transaction(
                    fingerprint=item["fingerprint"],
                    account_id=item["account_id"],
                    subaccount_type=item["subaccount_type"],
                    date=date.fromisoformat(item["date"]),
                    payee=item["payee"],
                    memo=item["memo"],
                    amount_cents=item["amount_cents"],
                    value_date=date.fromisoformat(item["value_date"])
                    if item.get("value_date")
                    else None,
                    transaction_type=item.get("transaction_type") or "",
                    reference=item.get("reference"),
                    raw_buchungstext=item.get("raw_buchungstext") or "",
                    raw_row=item.get("raw_row") or {},
                    category=item.get("category"),
                    classification_rule=item.get("classification_rule"),
                    group_id=item.get("group_id"),
                )
                for item in payload.get("transactions", [])
            ]
            _store_transactions_direct(
                conn,
                transactions,
                source_file=payload.get("source_file"),
                imported_at=timestamp,
            )
            return

        if mutation_type == "groups_applied":
            _apply_groups_direct(conn, payload.get("groups", {}))
            return

        if mutation_type == "rules_updated":
            return

        raise ValueError(f"Unknown mutation type: {mutation_type}")
