from datetime import date

from fastapi.testclient import TestClient

from penny.accounts import add_account
from penny.server import app
from penny.transactions import Transaction, generate_fingerprint, store_transactions


def make_transaction(
    account_id: int,
    tx_date: date,
    amount_cents: int,
    payee: str,
    *,
    category: str | None = None,
    raw_buchungstext: str = "",
) -> Transaction:
    fingerprint = generate_fingerprint(account_id, tx_date, amount_cents, payee, None)
    return Transaction(
        fingerprint=fingerprint,
        account_id=account_id,
        subaccount_type="giro",
        date=tx_date,
        payee=payee,
        memo="",
        amount_cents=amount_cents,
        value_date=None,
        transaction_type="",
        reference=None,
        raw_buchungstext=raw_buchungstext,
        raw_row={},
        category=category,
    )


def test_transactions_endpoint_uses_domain_filters(db):
    add_account("testbank")
    add_account("testbank")
    store_transactions(
        [
            make_transaction(1, date(2024, 1, 10), -1500, "Coffee Shop", category="food/coffee"),
            make_transaction(2, date(2024, 1, 15), 250000, "Salary", category="income/salary"),
            make_transaction(
                1,
                date(2024, 2, 3),
                -9900,
                "Spotify",
                category="subscriptions/music",
                raw_buchungstext="Spotify AB Stockholm",
            ),
        ]
    )

    client = TestClient(app)
    response = client.get(
        "/api/transactions",
        params={
            "from": "2024-02-01",
            "accounts": "1",
            "category": "subscriptions/",
            "q": "spotify",
            "tab": "expense",
            "neutralize": "false",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["total_cents"] == -9900
    assert [transaction["merchant"] for transaction in payload["transactions"]] == ["Spotify"]
