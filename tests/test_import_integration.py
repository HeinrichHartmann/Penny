import asyncio
from io import BytesIO

import pytest
from click.testing import CliRunner
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from penny.api.import_ import import_csv as import_csv_api
from penny.cli import main
from penny.transactions import count_transactions, list_transactions
from penny.vault import save_rules_snapshot

pytestmark = pytest.mark.integration


def test_import_creates_transactions_and_account(fixture_dir):
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    result = runner.invoke(main, ["import", "--csv-type", "comdirect", str(csv_path)])

    assert result.exit_code == 0
    assert "Detected: Comdirect" in result.output
    assert "Account: #1 (comdirect 9788862492)" in result.output
    assert "Sections: giro (2), visa (1)" in result.output
    assert "New: 3 transactions" in result.output
    assert "Duplicates: 0 (skipped)" in result.output

    list_result = runner.invoke(main, ["transactions", "list"])
    assert list_result.exit_code == 0
    assert "HOTEL EXAMPLE BERLIN" in list_result.output
    assert "AMAZON PAYMENTS EUROPE" in list_result.output

    assert count_transactions() == 3


def test_reimport_deduplicates(fixture_dir):
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    first = runner.invoke(main, ["import", str(csv_path)])
    assert first.exit_code == 0

    second = runner.invoke(main, ["import", str(csv_path)])
    assert second.exit_code == 0
    assert "New: 0 transactions" in second.output
    assert "Duplicates: 3 (skipped)" in second.output


def test_import_dry_run_does_not_persist(fixture_dir):
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    result = runner.invoke(main, ["import", "--dry-run", str(csv_path)])

    assert result.exit_code == 0
    assert "Account: [new] (comdirect 9788862492)" in result.output
    assert "Parsed: 3 transactions" in result.output

    list_result = runner.invoke(main, ["transactions", "list"])
    assert list_result.exit_code == 0
    assert "No transactions found." in list_result.output


def test_import_auto_classifies_with_default_rules(fixture_dir):
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    result = runner.invoke(main, ["import", str(csv_path)])

    assert result.exit_code == 0
    transactions = list_transactions(limit=None, neutralize=False, include_hidden=True)
    assert len(transactions) == 3
    assert all(transaction.category for transaction in transactions)


def test_api_import_fails_loudly_when_rules_are_invalid(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    save_rules_snapshot("def broken(:\n")

    with pytest.raises(HTTPException, match="rules evaluation failed") as exc_info:
        asyncio.run(
            import_csv_api(
                UploadFile(
                    file=BytesIO(csv_path.read_bytes()),
                    filename=csv_path.name,
                )
            )
        )

    assert exc_info.value.status_code == 500
    assert count_transactions() == 3
