from penny.ingest.banks.comdirect import ComdirectBank


def test_parse_skips_empty_section_without_header():
    parser = ComdirectBank()
    content = (
        '"Umsätze Girokonto";"Zeitraum: 01.01.2025 - 31.01.2025";\n'
        "\n"
        '"Buchungstag";"Wertstellung (Valuta)";"Vorgang";"Buchungstext";"Umsatz in EUR";\n'
        '"01.01.2025";"01.01.2025";"Lastschrift / Belastung";'
        '"Auftraggeber: AMAZON PAYMENTS EUROPE S.C.A. Buchungstext: Bestellung Ref. ABC/1";'
        '"-12,34";\n'
        "\n"
        '"Umsätze Tagesgeld PLUS-Konto";"Zeitraum: 01.01.2025 - 31.01.2025";\n'
        "\n"
        '"Keine Umsätze vorhanden.";\n'
    )

    transactions = parser.parse("umsaetze_1234567890_20260331-1351.csv", content, account_id=1)

    assert len(transactions) == 1
    assert transactions[0].payee == "AMAZON PAYMENTS EUROPE S.C.A."


def test_parse_merges_split_visa_rows_marked_as_new():
    parser = ComdirectBank()
    content = (
        '"Umsätze Visa-Karte (Kreditkarte)";"Zeitraum: 01.01.2025 - 31.01.2025";\n'
        "\n"
        '"Buchungstag";"Umsatztag";"Vorgang";"Referenz";"Buchungstext";"Umsatz in EUR";\n'
        '"23.01.2025";\n'
        '"neu";"22.01.2025";"Visa-Umsatz";"125012337815001";'
        '"DB FERNVERKEHR AG FRANKFURT 000";"-5,00";\n'
    )

    transactions = parser.parse("umsaetze_1234567890_20260331-1351.csv", content, account_id=1)

    assert len(transactions) == 1
    assert transactions[0].date.isoformat() == "2025-01-23"
    assert transactions[0].value_date.isoformat() == "2025-01-22"
    assert transactions[0].payee == "DB FERNVERKEHR AG FRANKFURT 000"
