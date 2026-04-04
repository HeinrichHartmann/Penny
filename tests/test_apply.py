from datetime import date

from click.testing import CliRunner

from penny.accounts import add_account
from penny.cli import main
from penny.db import init_default_db
from penny.transactions import Transaction, generate_fingerprint, list_transactions, store_transactions


def make_transaction(
    account_id: int,
    tx_date: date,
    amount_cents: int,
    payee: str,
    *,
    category: str | None = None,
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
        raw_buchungstext=payee,
        raw_row={},
        category=category,
    )


def test_apply_verbose_prints_matching_rule_names(monkeypatch, fixture_dir, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    import_result = runner.invoke(main, ["import", str(csv_path)])
    assert import_result.exit_code == 0

    rules_path = fixture_dir / "rules_primary.py"
    result = runner.invoke(main, ["apply", "-v", str(rules_path)])

    assert result.exit_code == 0
    assert "rule=salary" in result.output
    assert "rule=hotel" in result.output
    assert "rule=amazon" in result.output


def test_apply_trace_prints_rule_evaluation_order(monkeypatch, fixture_dir, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"

    import_result = runner.invoke(main, ["import", str(csv_path)])
    assert import_result.exit_code == 0

    rules_path = fixture_dir / "rules_primary.py"
    result = runner.invoke(main, ["apply", "-vv", str(rules_path)])

    assert result.exit_code == 0
    assert "[no] salary -> Income:Salary" in result.output
    assert "[yes] hotel -> Travel:Hotel" in result.output
    assert "[yes] amazon -> Shopping:GenericAmazon" in result.output


def test_apply_links_transfers_when_rules_define_predicate(monkeypatch, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    init_default_db()
    add_account("testbank")
    add_account("testbank")
    store_transactions(
        [
            make_transaction(1, date(2024, 3, 1), -10000, "Transfer Out"),
            make_transaction(2, date(2024, 3, 1), 10000, "Transfer In"),
        ]
    )

    rules_path = tmp_path / "rules.py"
    rules_path.write_text(
        """
from penny.classify import contains, rule

DEFAULT_CATEGORY = "uncategorized"
TRANSFER_PREFIX = "transfer/"
TRANSFER_WINDOW_DAYS = 1

@rule("transfer/private", name="transfer")
def transfer(tx):
    return contains(tx.payee, "transfer")

def in_same_transfer_group(a, b):
    return a.account_id != b.account_id and a.amount_cents == -b.amount_cents
""".strip()
        + "\n",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["apply", str(rules_path)])

    assert result.exit_code == 0
    assert "Transfers:" in result.output
    assert "Groups found: 1" in result.output

    raw_transactions = list_transactions(limit=None, neutralize=False)
    assert len(raw_transactions) == 2
    assert len({transaction.group_id for transaction in raw_transactions}) == 1
    assert raw_transactions[0].group_id != raw_transactions[0].fingerprint
