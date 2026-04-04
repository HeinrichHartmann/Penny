"""Tests for vault CLI commands."""

from click.testing import CliRunner
import pytest

from penny.cli import main
from penny.db import init_db
from penny.ingest import read_file_with_encoding
from penny.transactions import count_transactions
from penny.vault import IngestRequest, VaultConfig, ingest_csv

pytestmark = pytest.mark.integration


def test_vault_init_creates_first_entry():
    runner = CliRunner()

    result = runner.invoke(main, ["vault", "init"])

    assert result.exit_code == 0
    assert "Status: initialized" in result.output
    assert "Imports: 0" in result.output
    assert "Mutations: 0" in result.output


def test_vault_status_reports_entries(fixture_dir):
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    ingest_csv(
        IngestRequest(
            filename=csv_path.name,
            content=read_file_with_encoding(csv_path),
        ),
        config=VaultConfig(),
    )

    result = runner.invoke(main, ["vault", "status"])

    assert result.exit_code == 0
    assert "Initialized: yes" in result.output
    assert "Imports: 1" in result.output
    assert "Rules snapshots: 0" in result.output


def test_vault_replay_restores_projection(fixture_dir):
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    ingest_csv(
        IngestRequest(
            filename=csv_path.name,
            content=read_file_with_encoding(csv_path),
        ),
        config=VaultConfig(),
    )
    assert count_transactions() == 3

    init_db(None)
    assert count_transactions() == 0

    result = runner.invoke(main, ["vault", "replay"])

    assert result.exit_code == 0
    assert "Imports processed: 1" in result.output
    assert "ingest: 1" in result.output
    assert count_transactions() == 3
