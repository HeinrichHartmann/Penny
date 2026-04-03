from datetime import date

from penny.import_.detection import read_file_with_encoding
from penny.import_.parsers.comdirect import ComdirectParser
from penny.transactions import generate_fingerprint


def test_parse_comdirect_multi_section(fixture_dir):
    parser = ComdirectParser()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    content = read_file_with_encoding(csv_path)

    transactions = parser.parse(csv_path.name, content, account_id=1)

    assert len(transactions) == 3

    amazon = transactions[0]
    assert amazon.account_id == 1
    assert amazon.subaccount_type == "giro"
    assert amazon.date.isoformat() == "2026-02-27"
    assert amazon.value_date.isoformat() == "2026-02-27"
    assert amazon.payee == "AMAZON PAYMENTS EUROPE S.C.A."
    assert amazon.memo == "028-7214985-6053918 AMZN Mktp DE"
    assert amazon.reference == "9L2C28W229K9DKRY/41682"
    assert amazon.amount_cents == -3799

    visa = transactions[-1]
    assert visa.subaccount_type == "visa"
    assert visa.payee == "HOTEL EXAMPLE BERLIN"
    assert visa.memo == "HOTEL EXAMPLE BERLIN"
    assert visa.reference == "VISA-REF-123"
    assert visa.amount_cents == -4567


def test_fingerprint_deduplication():
    fp1 = generate_fingerprint(1, date(2026, 2, 27), -3799, "AMAZON", "9L2C28W229")
    fp2 = generate_fingerprint(1, date(2026, 2, 27), -3799, "AMAZON", "9L2C28W229")
    assert fp1 == fp2
