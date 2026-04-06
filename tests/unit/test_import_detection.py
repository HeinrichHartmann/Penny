import pytest

from penny.ingest import (
    CsvSource,
    DetectionError,
    match_file,
    match_source,
    read_file_with_encoding,
)
from penny.ingest.banks.comdirect import ComdirectBank


def test_comdirect_filename_match():
    parser = ComdirectBank()

    assert parser.filename_pattern.match("umsaetze_9788862492_20260331-1354.csv")
    assert parser.filename_pattern.match("umsaetze_9788862492_20260331-1354(1).csv")
    assert not parser.filename_pattern.match("other_format.csv")


def test_comdirect_detection(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    parser = ComdirectBank()
    source = CsvSource.from_path(csv_path)

    assert parser.match(source)

    result = parser.detect(source)
    assert result.bank == "comdirect"
    assert result.bank_account_number == "9788862492"
    assert result.detected_subaccounts == ["giro", "visa"]


def test_match_file_rejects_renamed_comdirect_export(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    content = read_file_with_encoding(csv_path)

    with pytest.raises(DetectionError) as exc:
        match_file("renamed.csv", content)

    assert "Expected: umsaetze_<account-number>_YYYYMMDD-HHMM.csv" in str(exc.value)


def test_match_file_uses_explicit_parser_type(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    content = read_file_with_encoding(csv_path)

    parser = match_file(csv_path.name, content, csv_type="comdirect")

    assert parser.bank == "comdirect"


def test_comdirect_extract_balances(fixture_dir):
    """Test that balance snapshots are extracted from 'Neuer Kontostand' rows."""
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    parser = ComdirectBank()
    source = CsvSource.from_path(csv_path)

    balances = parser.extract_balances(source)

    # The fixture has "Neuer Kontostand" only for giro (16,94 EUR)
    # (visa section only has "Alter Kontostand", not "Neuer Kontostand")
    assert len(balances) == 1

    # Check giro balance
    giro_balance = balances[0]
    assert giro_balance.subaccount_type == "giro"
    assert giro_balance.balance_cents == 1694  # 16,94 EUR
    assert giro_balance.snapshot_date.isoformat() == "2026-03-31"
    assert "umsaetze_9788862492_20260331-1354.csv" in giro_balance.note


def test_match_source_accepts_prefixed_comdirect_filename(fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    source = CsvSource.from_content(f"PI01231231_{csv_path.name}", csv_path.read_bytes())

    parser = match_source(source)
    result = parser.detect(source)

    assert source.filename == csv_path.name
    assert parser.bank == "comdirect"
    assert result.bank_account_number == "9788862492"
