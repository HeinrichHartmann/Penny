from datetime import date

from click.testing import CliRunner

from penny.accounts import add_account
from penny.cli import main
from penny.db import init_default_db
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


def test_transactions_list_matches_api_filters(monkeypatch, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    init_default_db()
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

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "transactions",
            "list",
            "--from",
            "2024-02-01",
            "--account",
            "1",
            "--category",
            "subscriptions/",
            "--query",
            "spotify",
            "--tab",
            "expense",
            "--no-neutralize",
        ],
    )

    assert result.exit_code == 0
    assert "Spotify" in result.output
    assert "Coffee Shop" not in result.output
    assert "Salary" not in result.output


def test_report_command_reuses_domain_report(monkeypatch, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    init_default_db()
    add_account("testbank")
    store_transactions(
        [
            make_transaction(1, date(2024, 2, 3), -9900, "Spotify", category="subscriptions/music"),
            make_transaction(1, date(2024, 2, 5), 250000, "Salary", category="income/salary"),
        ]
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "report",
            "--from",
            "2024-02-01",
            "--to",
            "2024-02-29",
            "--account",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "PENNY FINANCE REPORT" in result.output
    assert "Accounts: 1" in result.output
    assert "2024-02-01 to 2024-02-29" in result.output
    assert "income" in result.output
