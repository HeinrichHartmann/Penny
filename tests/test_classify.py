import asyncio

import pytest
from click.testing import CliRunner

from penny.api.rules import run_rules
from penny.classify import ClassificationDecision, contains, is_, load_rules, regexp
from penny.cli import main
from penny.transactions import TransactionStorage


def _import_fixture(runner: CliRunner, fixture_dir, tmp_path):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    result = runner.invoke(main, ["import", str(csv_path)], env={"PENNY_DATA_DIR": str(tmp_path)})
    assert result.exit_code == 0


def test_match_helpers_are_case_insensitive():
    assert is_(" AMAZON ", "amazon")
    assert contains("AMAZON PAYMENTS EUROPE", "payments")
    assert regexp("Lohn / Gehalt", r"gehalt")


def test_load_rules_preserves_file_order(fixture_dir):
    ruleset = load_rules(fixture_dir / "rules_reordered.py")

    assert [rule.name for rule in ruleset.rules] == [
        "salary",
        "hotel",
        "amazon_specific",
        "amazon",
    ]


def test_classify_updates_transactions(monkeypatch, fixture_dir, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    _import_fixture(runner, fixture_dir, tmp_path)

    rules_path = fixture_dir / "rules_primary.py"
    result = runner.invoke(main, ["classify", str(rules_path)])

    assert result.exit_code == 0
    assert "Rules: 3" in result.output
    assert "Matched: 3" in result.output
    assert "Default: 0" in result.output
    assert "Income:Salary: 1" in result.output
    assert "Travel:Hotel: 1" in result.output
    assert "Shopping:GenericAmazon: 1" in result.output

    storage = TransactionStorage(tmp_path / "penny.db")
    transactions = storage.list_transactions(limit=None)
    categories = {transaction.payee: transaction.category for transaction in transactions}
    rules = {transaction.payee: transaction.classification_rule for transaction in transactions}

    assert categories["Example Employer"] == "Income:Salary"
    assert categories["HOTEL EXAMPLE BERLIN"] == "Travel:Hotel"
    assert categories["AMAZON PAYMENTS EUROPE S.C.A."] == "Shopping:GenericAmazon"
    assert rules["AMAZON PAYMENTS EUROPE S.C.A."] == "amazon"


def test_classify_can_reclassify_with_different_rules(monkeypatch, fixture_dir, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    _import_fixture(runner, fixture_dir, tmp_path)

    first_rules = fixture_dir / "rules_primary.py"
    second_rules = fixture_dir / "rules_reordered.py"

    first = runner.invoke(main, ["classify", str(first_rules)])
    assert first.exit_code == 0

    second = runner.invoke(main, ["classify", str(second_rules)])
    assert second.exit_code == 0
    assert "Shopping:SpecificAmazon: 1" in second.output

    storage = TransactionStorage(tmp_path / "penny.db")
    transactions = storage.list_transactions(limit=None)
    amazon = next(transaction for transaction in transactions if "AMAZON" in transaction.payee)

    assert amazon.category == "Shopping:SpecificAmazon"
    assert amazon.classification_rule == "amazon_specific"


def test_api_run_rules_applies_default_category_to_unmatched(monkeypatch, fixture_dir, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    _import_fixture(runner, fixture_dir, tmp_path)

    rules_path = tmp_path / "rules.py"
    rules_path.write_text(
        """
from penny.classify import contains, rule

DEFAULT_CATEGORY = "NeedsReview"

@rule("Income:Salary", name="salary")
def salary(transaction):
    return contains(transaction.payee, "Employer")
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = asyncio.run(run_rules())

    assert result["status"] == "success"
    assert result["stats"]["matched_count"] == 1
    assert result["stats"]["unmatched_count"] == 2
    assert result["stats"]["categories"] == [
        {"category": "Income:Salary", "count": 1},
        {"category": "NeedsReview", "count": 2},
    ]

    storage = TransactionStorage(tmp_path / "penny.db")
    transactions = storage.list_transactions(limit=None, consolidated=False)
    categories = {transaction.payee: transaction.category for transaction in transactions}

    assert categories["Example Employer"] == "Income:Salary"
    assert categories["HOTEL EXAMPLE BERLIN"] == "NeedsReview"
    assert categories["AMAZON PAYMENTS EUROPE S.C.A."] == "NeedsReview"
    assert all(transaction.category for transaction in transactions)


def test_apply_classifications_requires_complete_pass(monkeypatch, fixture_dir, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    _import_fixture(runner, fixture_dir, tmp_path)

    storage = TransactionStorage(tmp_path / "penny.db")
    transactions = storage.list_transactions(limit=None, consolidated=False)

    with pytest.raises(RuntimeError, match="without a category"):
        storage.apply_classifications(
            [
                ClassificationDecision(
                    fingerprint=transactions[0].fingerprint,
                    category="TestOnly",
                    rule_name="manual",
                )
            ]
        )

    after = storage.list_transactions(limit=None, consolidated=False)
    assert all(transaction.category is None for transaction in after)
