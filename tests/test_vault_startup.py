"""Tests for vault startup bootstrap."""

import pytest

from penny.accounts import add_account, list_accounts
from penny.transactions import count_transactions
from penny.vault import (
    IngestRequest,
    LogManager,
    VaultConfig,
    bootstrap_application_state,
    ingest_csv,
)
from penny.ingest import read_file_with_encoding

pytestmark = pytest.mark.integration


def test_bootstrap_initializes_empty_vault(tmp_path):
    config = VaultConfig(tmp_path / "vault")

    result = bootstrap_application_state(config)
    log = LogManager(config)

    assert result.init_entry_created is True
    assert result.replay_result.entries_processed == 1
    assert result.replay_result.entries_by_type == {"init": 1}
    assert log.count() == 1
    assert log.latest_entry().entry_type == "init"


def test_bootstrap_replays_existing_ingests(tmp_path, fixture_dir):
    config = VaultConfig(tmp_path / "vault")
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


def test_bootstrap_clears_projection_drift(tmp_path, fixture_dir):
    config = VaultConfig(tmp_path / "vault")
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    ingest_csv(
        IngestRequest(
            filename=csv_path.name,
            content=read_file_with_encoding(csv_path),
        ),
        config=config,
    )
    add_account("manual", bank_account_number="99999999")

    assert len(list_accounts()) == 2

    bootstrap_application_state(config)

    accounts = list_accounts()
    assert len(accounts) == 1
    assert accounts[0].bank == "comdirect"
    assert count_transactions() == 3
