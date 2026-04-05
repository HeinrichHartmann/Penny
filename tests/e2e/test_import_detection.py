from click.testing import CliRunner

from penny.cli import main
from penny.ingest import read_file_with_encoding


def test_import_help_lists_supported_csv_types():
    runner = CliRunner()
    result = runner.invoke(main, ["import", "--help"])

    assert result.exit_code == 0
    assert "--csv-type" in result.output
    assert "comdirect" in result.output


def test_import_cli_rejects_renamed_file(fixture_dir, tmp_path):
    runner = CliRunner()
    renamed = tmp_path / "renamed.csv"
    content = read_file_with_encoding(fixture_dir / "umsaetze_9788862492_20260331-1354.csv")
    renamed.write_text(content, encoding="utf-8")

    result = runner.invoke(main, ["import", str(renamed)])

    assert result.exit_code != 0
    assert "Filename does not match expected export format." in result.output
    assert "umsaetze_<account-number>_YYYYMMDD-HHMM.csv" in result.output
