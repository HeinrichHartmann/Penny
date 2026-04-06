"""Tests for vault startup bootstrap."""

import asyncio

import pytest

from penny.accounts import add_account, list_accounts
from penny.api.accounts import update_account
from penny.db import transaction
from penny.ingest import read_file_with_encoding
from penny.transactions import count_transactions
from penny.vault import (
    IngestRequest,
    VaultConfig,
    bootstrap_application_state,
    ingest_csv,
    latest_rules_path,
)

pytestmark = pytest.mark.integration


def test_bootstrap_initializes_empty_vault(fresh_runtime):
    config = VaultConfig(fresh_runtime.vault_dir)

    result = bootstrap_application_state(config)

    assert result.init_entry_created is True
    # Empty vault: no entries to replay
    assert result.replay_result.entries_processed == 0
    assert config.transactions_dir.exists()
    assert config.rules_dir.exists()
    assert config.balance_dir.exists()
    assert config.ledger_path.exists()
    assert latest_rules_path(config) is not None


def test_bootstrap_replays_existing_ingests(fresh_runtime, fixture_dir):
    config = VaultConfig(fresh_runtime.vault_dir)
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    ingest_csv(
        IngestRequest(
            filename=csv_path.name,
            content=read_file_with_encoding(csv_path),
        ),
        config=config,
    )
    assert count_transactions() == 3

    result = bootstrap_application_state(config)

    assert result.init_entry_created is False
    assert result.replay_result.entries_processed == 1
    assert result.replay_result.entries_by_type == {"ingest": 1}
    assert count_transactions() == 3


def test_bootstrap_clears_projection_drift(fresh_runtime, fixture_dir):
    config = VaultConfig(fresh_runtime.vault_dir)
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    ingest_csv(
        IngestRequest(
            filename=csv_path.name,
            content=read_file_with_encoding(csv_path),
        ),
        config=config,
    )
    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO accounts (
                bank, display_name, iban, holder, notes,
                balance_cents, balance_date, created_at, updated_at, hidden
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                "manual",
                None,
                None,
                None,
                None,
                None,
                None,
                "2026-01-01T00:00:00Z",
                "2026-01-01T00:00:00Z",
            ),
        )

    assert len(list_accounts()) == 2

    bootstrap_application_state(config)

    accounts = list_accounts()
    assert len(accounts) == 1
    assert accounts[0].bank == "comdirect"
    assert count_transactions() == 3


def test_bootstrap_replays_account_naming_mutation(fresh_runtime, fixture_dir):
    config = VaultConfig(fresh_runtime.vault_dir)
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    ingest_csv(
        IngestRequest(
            filename=csv_path.name,
            content=read_file_with_encoding(csv_path),
        ),
        config=config,
    )

    asyncio.run(update_account(1, display_name="Private Main"))

    bootstrap_application_state(config)

    accounts = list_accounts()
    assert len(accounts) == 1
    assert accounts[0].display_name == "Private Main"


def test_bootstrap_replays_manual_account_creation(fresh_runtime):
    config = VaultConfig(fresh_runtime.vault_dir)

    add_account("manual", bank_account_number="99999999")

    bootstrap_application_state(config)

    accounts = list_accounts()
    assert len(accounts) == 1
    assert accounts[0].bank == "manual"
    assert accounts[0].bank_account_numbers == ["99999999"]
