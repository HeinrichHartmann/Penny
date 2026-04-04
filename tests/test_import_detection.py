import pytest
from click.testing import CliRunner

from penny.cli import main
from penny.ingest import DetectionError, match_file, read_file_with_encoding
from penny.ingest.banks.comdirect import ComdirectBank


def test_comdirect_filename_match():
    parser = ComdirectBank()

    assert parser.filename_pattern.match("umsaetze_9788862492_20260331-1354.csv")
    assert parser.filename_pattern.match("umsaetze_9788862492_20260331-1354(1).csv")
    assert not parser.filename_pattern.match("other_format.csv")


def test_comdirect_detection(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    parser = ComdirectBank()
    content = read_file_with_encoding(csv_path)

    assert parser.match(csv_path.name, content)

    result = parser.detect(csv_path.name, content)
    assert result.bank == "comdirect"
    assert result.bank_account_number == "9788862492"
    assert result.detected_subaccounts == ["giro", "visa"]


def test_match_file_rejects_renamed_comdirect_export(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    content = read_file_with_encoding(csv_path)

    with pytest.raises(DetectionError) as exc:
        match_file("renamed.csv", content)

    assert "Expected: umsaetze_<account-number>_YYYYMMDD-HHMM.csv" in str(exc.value)


@pytest.mark.integration
def test_import_help_lists_supported_csv_types():
    runner = CliRunner()
    result = runner.invoke(main, ["import", "--help"])

    assert result.exit_code == 0
    assert "--csv-type" in result.output
    assert "comdirect" in result.output


def test_match_file_uses_explicit_parser_type(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    content = read_file_with_encoding(csv_path)

    parser = match_file(csv_path.name, content, csv_type="comdirect")

    assert parser.bank == "comdirect"


@pytest.mark.integration
def test_import_cli_rejects_renamed_file(fixture_dir, tmp_path):
    runner = CliRunner()
    renamed = tmp_path / "renamed.csv"
    content = read_file_with_encoding(fixture_dir / "umsaetze_9788862492_20260331-1354.csv")
    renamed.write_text(content, encoding="utf-8")

    result = runner.invoke(main, ["import", str(renamed)])

    assert result.exit_code != 0
    assert "Filename does not match expected export format." in result.output
    assert "umsaetze_<account-number>_YYYYMMDD-HHMM.csv" in result.output
