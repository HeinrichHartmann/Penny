"""Apply log entries to the SQLite projection."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from penny.vault.log import LogEntry
from penny.vault.manifests import (
    AccountCreatedManifest,
    AccountHiddenManifest,
    AccountUpdatedManifest,
    BalanceSnapshotManifest,
    IngestManifest,
    RulesManifest,
)
from penny.vault.mutations import MutationRow

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
    from penny.accounts import (
        Subaccount,
        _create_account_direct,
        _find_account_by_bank_account_number_in_conn,
        _get_account_in_conn,
        _upsert_subaccounts_direct,
    )
    from penny.db import init_default_db, transaction
    from penny.ingest import match_file, read_file_with_encoding
    from penny.transactions import _store_transactions_direct

    manifest: IngestManifest = entry.read_manifest()  # type: ignore

    if manifest.type != "ingest":
        raise ValueError(f"Expected ingest manifest, got {manifest.type}")

    # Initialize DB (idempotent, initializes schema too)
    init_default_db()

    all_transactions: list[Transaction] = []
    parser_name = manifest.parser
    account = None

    with transaction() as conn:
        for csv_filename in manifest.csv_files:
            csv_path = entry.path / csv_filename
            content = read_file_with_encoding(csv_path)

            parser = match_file(csv_filename, content, csv_type=manifest.parser)
            parser_name = parser.name

            detection = parser.detect(csv_filename, content)
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
                    subaccounts={
                        subaccount_type: Subaccount(type=subaccount_type)
                        for subaccount_type in detection.detected_subaccounts
                    },
                    created_at=manifest.timestamp,
                    updated_at=manifest.timestamp,
                )
            else:
                _upsert_subaccounts_direct(conn, account.id, detection.detected_subaccounts)
                refreshed = _get_account_in_conn(conn, account.id, include_hidden=True)
                if refreshed is not None:
                    account = refreshed

            transactions = parser.parse(csv_filename, content, account_id=account.id)
            all_transactions.extend(transactions)

        if account is None:
            raise ValueError("No CSV files in ingest entry")

        new_count, duplicate_count = _store_transactions_direct(
            conn,
            all_transactions,
            source_file=manifest.csv_files[0] if manifest.csv_files else "unknown",
            imported_at=manifest.timestamp,
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
            _apply_account_updated(entry, manifest)  # type: ignore
        case "account_hidden":
            _apply_account_hidden(entry, manifest)  # type: ignore
        case "balance_snapshot":
            _apply_balance_snapshot(entry, manifest)  # type: ignore
        case "rules":
            _apply_rules(entry, manifest)  # type: ignore
        case _:
            raise ValueError(f"Unknown manifest type: {manifest.type}")


def _apply_account_created(entry: LogEntry, manifest: AccountCreatedManifest) -> None:
    """Apply account_created entry."""
    from penny.accounts import _create_account_direct
    from penny.db import transaction

    with transaction() as conn:
        _create_account_direct(
            conn,
            bank=manifest.bank,
            bank_account_numbers=[manifest.bank_account_number]
            if manifest.bank_account_number
            else [],
            display_name=manifest.display_name,
            iban=manifest.iban,
            created_at=manifest.timestamp,
            updated_at=manifest.timestamp,
        )


def _apply_account_updated(entry: LogEntry, manifest: AccountUpdatedManifest) -> None:
    """Apply account_updated entry."""
    from penny.accounts import _update_account_metadata_direct
    from penny.db import transaction

    with transaction() as conn:
        _update_account_metadata_direct(
            conn,
            manifest.account_id,
            updated_at=manifest.timestamp,
            **manifest.fields,
        )


def _apply_account_hidden(entry: LogEntry, manifest: AccountHiddenManifest) -> None:
    """Apply account_hidden entry."""
    from penny.accounts import _soft_delete_account_direct
    from penny.db import transaction

    with transaction() as conn:
        _soft_delete_account_direct(
            conn,
            manifest.account_id,
            updated_at=manifest.timestamp,
        )


def _apply_balance_snapshot(entry: LogEntry, manifest: BalanceSnapshotManifest) -> None:
    """Apply balance_snapshot entry."""
    from penny.accounts import update_account_balance

    snapshot_date = date.fromisoformat(manifest.snapshot_date)
    update_account_balance(
        manifest.account_id,
        balance_cents=manifest.balance_cents,
        balance_date=snapshot_date,
    )


def _apply_rules(entry: LogEntry, manifest: RulesManifest) -> None:
    """Apply rules entry by ensuring the snapshot exists on disk."""
    return None


def apply_mutation(row: MutationRow) -> None:
    """Apply a mutation row directly to the SQLite projection."""
    from penny.accounts import (
        Subaccount,
        _create_account_direct,
        _soft_delete_account_direct,
        _update_account_metadata_direct,
    )
    from penny.db import transaction
    from penny.transactions import _apply_classifications_direct, _apply_groups_direct

    payload = json.loads(row.payload_json)

    with transaction() as conn:
        if row.type == "account_created":
            _create_account_direct(
                conn,
                bank=payload["bank"],
                bank_account_numbers=payload.get("bank_account_numbers") or [],
                display_name=payload.get("display_name"),
                iban=payload.get("iban"),
                holder=payload.get("holder"),
                notes=payload.get("notes"),
                balance_cents=payload.get("balance_cents"),
                balance_date=date.fromisoformat(payload["balance_date"])
                if payload.get("balance_date")
                else None,
                subaccounts={
                    item["type"]: Subaccount(
                        type=item["type"], display_name=item.get("display_name")
                    )
                    for item in payload.get("subaccounts", [])
                },
                created_at=row.timestamp,
                updated_at=row.timestamp,
            )
            return

        if row.type == "account_updated":
            _update_account_metadata_direct(
                conn,
                int(row.entity_id),
                updated_at=row.timestamp,
                **payload,
            )
            return

        if row.type == "account_hidden":
            _soft_delete_account_direct(conn, int(row.entity_id), updated_at=row.timestamp)
            return

        if row.type == "subaccounts_upserted":
            from penny.accounts import _upsert_subaccounts_direct

            _upsert_subaccounts_direct(
                conn, int(row.entity_id), payload.get("subaccount_types", [])
            )
            return

        if row.type == "transactions_stored":
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
                imported_at=row.timestamp,
            )
            return

        if row.type == "classifications_applied":
            from penny.classify.engine import ClassificationDecision

            decisions = [
                ClassificationDecision(
                    fingerprint=item["fingerprint"],
                    category=item["category"],
                    rule_name=item["rule_name"],
                )
                for item in payload.get("decisions", [])
            ]
            _apply_classifications_direct(conn, decisions, classified_at=row.timestamp)
            return

        if row.type == "groups_applied":
            _apply_groups_direct(conn, payload.get("groups", {}))
            return

        if row.type == "rules_updated":
            return

        raise ValueError(f"Unknown mutation type: {row.type}")
