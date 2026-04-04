import pytest
from click.testing import CliRunner

from penny.cli import main
from penny.transactions import count_transactions

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
