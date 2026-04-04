from penny.ingest.formats.buchungstext import extract_memo, extract_payee, extract_reference


def test_extract_payee_auftraggeber():
    text = (
        "Auftraggeber: AMAZON PAYMENTS EUROPE S.C.A. "
        "Buchungstext: 028-7214985 Ref. 9L2C28W229"
    )
    assert extract_payee(text) == "AMAZON PAYMENTS EUROPE S.C.A."


def test_extract_memo():
    text = (
        "Auftraggeber: AMAZON "
        "Buchungstext: 028-7214985-6053918 AMZN Mktp DE Ref. 9L2C28W229"
    )
    assert extract_memo(text) == "028-7214985-6053918 AMZN Mktp DE"


def test_extract_reference():
    text = "Auftraggeber: AMAZON Buchungstext: Test Ref. 9L2C28W229K9DKRY/41682"
    assert extract_reference(text) == "9L2C28W229K9DKRY/41682"
