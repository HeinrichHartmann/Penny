from datetime import date

from penny.accounts import add_account
from penny.transactions import (
    Transaction,
    TransactionFilter,
    filter_transactions,
    generate_fingerprint,
    list_transactions,
    store_transactions,
)


def make_transaction(
    account_id: int,
    tx_date: date,
    amount_cents: int,
    payee: str,
    *,
    category: str | None = None,
    raw_buchungstext: str = "",
) -> Transaction:
    fingerprint = generate_fingerprint(account_id, "giro", tx_date, amount_cents, payee, None)
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


def test_filter_transactions_applies_reusable_filters():
    transactions = [
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

    filtered = filter_transactions(
        transactions,
        TransactionFilter(
            from_date=date(2024, 2, 1),
            account_ids=frozenset({1}),
            category_prefix="subscriptions/",
            search_query="stockholm",
            tab="expense",
        ),
    )

    assert [transaction.payee for transaction in filtered] == ["Spotify"]


def test_list_transactions_supports_reusable_filters(db):
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

    transactions = list_transactions(
        filters=TransactionFilter(
            from_date=date(2024, 2, 1),
            account_ids=frozenset({1}),
            category_prefix="subscriptions/",
            search_query="spotify",
            tab="expense",
        ),
        limit=None,
        neutralize=False,
    )

    assert [transaction.payee for transaction in transactions] == ["Spotify"]


def test_list_transactions_applies_limit_after_filtering(db):
    add_account("testbank")
    store_transactions(
        [
            make_transaction(1, date(2024, 3, 3), -1000, "Coffee 3", category="food/coffee"),
            make_transaction(1, date(2024, 3, 2), -1000, "Coffee 2", category="food/coffee"),
            make_transaction(1, date(2024, 3, 1), -1000, "Coffee 1", category="food/coffee"),
        ]
    )

    transactions = list_transactions(
        filters=TransactionFilter(category_prefix="food/"),
        limit=2,
        neutralize=False,
    )

    assert [transaction.payee for transaction in transactions] == ["Coffee 3", "Coffee 2"]
