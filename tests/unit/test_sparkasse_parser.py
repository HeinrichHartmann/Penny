import pytest

from penny.ingest import (
    CsvSource,
    DetectionError,
    match_file,
    match_source,
    read_file_with_encoding,
)
from penny.ingest.banks.sparkasse import SparkasseBank


def test_sparkasse_filename_match():
    bank = SparkasseBank()

    assert bank.filename_pattern.match("20260401-12345678-umsatz-camt52v8.CSV")
    assert bank.filename_pattern.match("20260401-12345678-umsatz-camt52v8.csv")
    assert bank.filename_pattern.match("20260402-97002927-umsatz-camt52v8(1).CSV")
    assert bank.filename_pattern.match("20260401-12345678-umsatz-camt52v8(2).csv")
    assert not bank.filename_pattern.match("umsaetze_12345678_20260401-1234.csv")
    assert not bank.filename_pattern.match("other_format.csv")


def test_sparkasse_detection(fixture_dir):
    csv_path = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"
    bank = SparkasseBank()
    source = CsvSource.from_path(csv_path)

    assert bank.match(source)

    result = bank.detect(source)
    assert result.bank == "sparkasse"
    assert result.bank_account_number == "12345678"
    assert result.iban == "DE89370400440532013000"
    assert result.detected_subaccounts == ["giro"]


def test_sparkasse_parse(fixture_dir):
    csv_path = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"
    bank = SparkasseBank()
    source = CsvSource.from_path(csv_path)

    transactions = bank.parse(source, account_id=1)

    assert len(transactions) == 3

    # First transaction: fee
    fee = transactions[0]
    assert fee.account_id == 1
    assert fee.subaccount_type == "giro"
    assert fee.date.isoformat() == "2026-04-01"
    assert fee.amount_cents == -990
    assert fee.memo == "Kontofuehrung April"

    # Second transaction: salary
    salary = transactions[1]
    assert salary.date.isoformat() == "2026-03-28"
    assert salary.payee == "Beispiel Arbeitgeber GmbH"
    assert salary.amount_cents == 250000
    assert salary.reference == "SALARY-2026-03"

    # Third transaction: rent
    rent = transactions[2]
    assert rent.date.isoformat() == "2026-03-15"
    assert rent.payee == "Hausverwaltung Muster"
    assert rent.amount_cents == -85000


def test_match_file_detects_sparkasse(fixture_dir):
    csv_path = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"
    content = read_file_with_encoding(csv_path)

    parser = match_file(csv_path.name, content)

    assert parser.bank == "sparkasse"


def test_match_file_rejects_renamed_sparkasse_export(fixture_dir):
    csv_path = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"
    content = read_file_with_encoding(csv_path)

    with pytest.raises(DetectionError) as exc:
        match_file("renamed.csv", content)

    assert "YYYYMMDD-ACCOUNTNUMBER-umsatz-camt52v8.CSV" in str(exc.value)


def test_match_source_accepts_prefixed_sparkasse_filename(fixture_dir):
    csv_path = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"
    source = CsvSource.from_content(f"PI01231231_{csv_path.name}", csv_path.read_bytes())

    parser = match_source(source)
    result = parser.detect(source)

    assert source.filename == csv_path.name
    assert parser.bank == "sparkasse"
    assert result.bank_account_number == "12345678"
