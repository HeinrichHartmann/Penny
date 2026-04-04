"""Single write surface for DB-affecting mutations."""

from __future__ import annotations

from contextlib import closing
from datetime import date
from typing import TYPE_CHECKING

from penny.db import connect
from penny.vault.config import VaultConfig
from penny.vault.mutations import MutationLog

if TYPE_CHECKING:
    from penny.accounts import Account, Subaccount
    from penny.classify import ClassificationDecision
    from penny.transactions import Transaction


def _apply_mutations(config: VaultConfig, *, upto_seq: int | None = None) -> int:
    from penny.vault.replay import apply_pending_mutations

    return apply_pending_mutations(config, upto_seq=upto_seq).entries_processed


def create_account(
    *,
    bank: str,
    bank_account_numbers: list[str] | None = None,
    display_name: str | None = None,
    iban: str | None = None,
    holder: str | None = None,
    notes: str | None = None,
    balance_cents: int | None = None,
    balance_date: date | None = None,
    subaccounts: dict[str, "Subaccount"] | None = None,
    config: VaultConfig | None = None,
) -> "Account":
    from penny.accounts import get_account

    cfg = config or VaultConfig()
    row = MutationLog(cfg).append(
        "account_created",
        entity_type="account",
        payload={
            "bank": bank,
            "bank_account_numbers": list(bank_account_numbers or []),
            "display_name": display_name,
            "iban": iban,
            "holder": holder,
            "notes": notes,
            "balance_cents": balance_cents,
            "balance_date": balance_date.isoformat() if balance_date else None,
            "subaccounts": [
                {"type": subaccount.type, "display_name": subaccount.display_name}
                for subaccount in (subaccounts or {}).values()
            ],
        },
    )
    _apply_mutations(cfg, upto_seq=row.seq)
    account = _lookup_account_created_from_row(row.seq)
    if account is None:
        raise RuntimeError("Account creation was not applied")
    return account


def update_account(
    account_id: int,
    *,
    display_name: str | None = None,
    iban: str | None = None,
    holder: str | None = None,
    notes: str | None = None,
    config: VaultConfig | None = None,
) -> "Account | None":
    from penny.accounts import get_account

    changes = {}
    if display_name is not None:
        changes["display_name"] = display_name
    if iban is not None:
        changes["iban"] = iban
    if holder is not None:
        changes["holder"] = holder
    if notes is not None:
        changes["notes"] = notes

    if not changes:
        return get_account(account_id, include_hidden=True)

    cfg = config or VaultConfig()
    row = MutationLog(cfg).append(
        "account_updated",
        entity_type="account",
        entity_id=account_id,
        payload=changes,
    )
    _apply_mutations(cfg, upto_seq=row.seq)
    return get_account(account_id, include_hidden=True)


def hide_account(account_id: int, config: VaultConfig | None = None) -> bool:
    from penny.accounts import get_account

    cfg = config or VaultConfig()
    row = MutationLog(cfg).append(
        "account_hidden",
        entity_type="account",
        entity_id=account_id,
        payload={},
    )
    _apply_mutations(cfg, upto_seq=row.seq)
    account = get_account(account_id, include_hidden=True)
    return account is not None and account.hidden


def upsert_subaccounts(
    account_id: int,
    subaccount_types: list[str],
    config: VaultConfig | None = None,
) -> None:
    if not subaccount_types:
        return

    cfg = config or VaultConfig()
    row = MutationLog(cfg).append(
        "subaccounts_upserted",
        entity_type="account",
        entity_id=account_id,
        payload={"subaccount_types": sorted(set(subaccount_types))},
    )
    _apply_mutations(cfg, upto_seq=row.seq)


def apply_classifications(
    decisions: list["ClassificationDecision"],
    config: VaultConfig | None = None,
) -> tuple[int, int]:
    from penny.transactions import count_transactions

    cfg = config or VaultConfig()
    row = MutationLog(cfg).append(
        "classifications_applied",
        entity_type="transactions",
        payload={
            "decisions": [
                {
                    "fingerprint": decision.fingerprint,
                    "category": decision.category,
                    "rule_name": decision.rule_name,
                }
                for decision in decisions
            ]
        },
    )
    _apply_mutations(cfg, upto_seq=row.seq)
    total = count_transactions()
    return len(decisions), total - len(decisions)


def apply_groups(
    groups: dict[str, str],
    config: VaultConfig | None = None,
) -> tuple[int, int]:
    from penny.transactions import list_transactions

    cfg = config or VaultConfig()
    row = MutationLog(cfg).append(
        "groups_applied",
        entity_type="transactions",
        payload={"groups": groups},
    )
    _apply_mutations(cfg, upto_seq=row.seq)
    raw = list_transactions(limit=None, neutralize=False)
    grouped = sum(1 for tx in raw if tx.group_id != tx.fingerprint)
    standalone = sum(1 for tx in raw if tx.group_id == tx.fingerprint)
    return grouped, standalone


def store_transactions(
    transactions: list["Transaction"],
    *,
    source_file: str | None = None,
    config: VaultConfig | None = None,
) -> tuple[int, int]:
    from penny.transactions import count_transactions

    cfg = config or VaultConfig()
    before = count_transactions()
    row = MutationLog(cfg).append(
        "transactions_stored",
        entity_type="transactions",
        payload={
            "source_file": source_file,
            "transactions": [
                {
                    "fingerprint": tx.fingerprint,
                    "account_id": tx.account_id,
                    "subaccount_type": tx.subaccount_type,
                    "date": tx.date.isoformat(),
                    "payee": tx.payee,
                    "memo": tx.memo,
                    "amount_cents": tx.amount_cents,
                    "value_date": tx.value_date.isoformat() if tx.value_date else None,
                    "transaction_type": tx.transaction_type,
                    "reference": tx.reference,
                    "raw_buchungstext": tx.raw_buchungstext,
                    "raw_row": tx.raw_row,
                    "category": tx.category,
                    "classification_rule": tx.classification_rule,
                    "group_id": tx.group_id,
                }
                for tx in transactions
            ],
        },
    )
    _apply_mutations(cfg, upto_seq=row.seq)
    after = count_transactions()
    new_count = after - before
    return new_count, len(transactions) - new_count


def _lookup_account_created_from_row(_seq: int):
    from penny.accounts import get_account

    with closing(connect()) as conn:
        row = conn.execute("SELECT MAX(id) AS id FROM accounts").fetchone()
    if row is None or row["id"] is None:
        return None
    return get_account(int(row["id"]), include_hidden=True)
