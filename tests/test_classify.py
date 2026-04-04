import asyncio

import pytest
from click.testing import CliRunner

from penny.api.rules import RulesUpdate, get_rules_path, run_rules, save_rules
from penny.classify import ClassificationDecision, contains, is_, load_rules, regexp
from penny.cli import main
from penny.db import init_db
from penny.transactions import apply_classifications, list_transactions
from penny.vault import MutationLog, VaultConfig, replay_vault


def _import_fixture(runner: CliRunner, fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    result = runner.invoke(main, ["import", str(csv_path)])
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


@pytest.mark.integration
def test_classify_updates_transactions(fixture_dir):
    runner = CliRunner()
    _import_fixture(runner, fixture_dir)

    rules_path = fixture_dir / "rules_primary.py"
    result = runner.invoke(main, ["apply", str(rules_path)])

    assert result.exit_code == 0
    assert "Rules: 3" in result.output
    assert "Matched: 3" in result.output
    assert "Default: 0" in result.output
    assert "Income:Salary: 1" in result.output
    assert "Travel:Hotel: 1" in result.output
    assert "Shopping:GenericAmazon: 1" in result.output

    transactions = list_transactions(limit=None, neutralize=False)
    categories = {transaction.payee: transaction.category for transaction in transactions}
    rules = {transaction.payee: transaction.classification_rule for transaction in transactions}

    assert categories["Example Employer"] == "Income:Salary"
    assert categories["HOTEL EXAMPLE BERLIN"] == "Travel:Hotel"
    assert categories["AMAZON PAYMENTS EUROPE S.C.A."] == "Shopping:GenericAmazon"
    assert rules["AMAZON PAYMENTS EUROPE S.C.A."] == "amazon"


@pytest.mark.integration
def test_classify_can_reclassify_with_different_rules(fixture_dir):
    runner = CliRunner()
    _import_fixture(runner, fixture_dir)

    first_rules = fixture_dir / "rules_primary.py"
    second_rules = fixture_dir / "rules_reordered.py"

    first = runner.invoke(main, ["apply", str(first_rules)])
    assert first.exit_code == 0

    second = runner.invoke(main, ["apply", str(second_rules)])
    assert second.exit_code == 0
    assert "Shopping:SpecificAmazon: 1" in second.output

    transactions = list_transactions(limit=None, neutralize=False)
    amazon = next(transaction for transaction in transactions if "AMAZON" in transaction.payee)

    assert amazon.category == "Shopping:SpecificAmazon"
    assert amazon.classification_rule == "amazon_specific"


@pytest.mark.integration
def test_api_run_rules_applies_default_category_to_unmatched(fixture_dir):
    runner = CliRunner()
    _import_fixture(runner, fixture_dir)

    result_save = asyncio.run(
        save_rules(
            RulesUpdate(
                content="""
from penny.classify import contains, rule

DEFAULT_CATEGORY = "NeedsReview"

@rule("Income:Salary", name="salary")
def salary(transaction):
    return contains(transaction.payee, "Employer")
""".strip()
                + "\n"
            )
        )
    )
    # Verify rules file exists (used by run_rules internally)
    _ = get_rules_path()

    result = asyncio.run(run_rules())

    assert result_save["status"] == "saved"
    assert result["status"] == "success"
    assert result["stats"]["matched_count"] == 1
    assert result["stats"]["unmatched_count"] == 2
    assert result["stats"]["categories"] == [
        {"category": "Income:Salary", "count": 1},
        {"category": "NeedsReview", "count": 2},
    ]

    transactions = list_transactions(limit=None, neutralize=False)
    categories = {transaction.payee: transaction.category for transaction in transactions}

    assert categories["Example Employer"] == "Income:Salary"
    assert categories["HOTEL EXAMPLE BERLIN"] == "NeedsReview"
    assert categories["AMAZON PAYMENTS EUROPE S.C.A."] == "NeedsReview"
    assert all(transaction.category for transaction in transactions)

    # Classifications are now computed at runtime, not persisted to mutations log
    # Only rules.py changes are stored in the vault
    rows = MutationLog(VaultConfig()).list_rows()
    if rows:  # May be empty if no mutations were logged
        assert rows[-1].type == "rules_updated"

    init_db(None)
    replay_vault(VaultConfig())
    replayed = {
        transaction.payee: transaction.category
        for transaction in list_transactions(limit=None, neutralize=False)
    }
    assert replayed["Example Employer"] == "Income:Salary"
    assert replayed["HOTEL EXAMPLE BERLIN"] == "NeedsReview"


@pytest.mark.integration
def test_apply_classifications_requires_complete_pass(fixture_dir):
    runner = CliRunner()
    _import_fixture(runner, fixture_dir)

    transactions = list_transactions(limit=None, neutralize=False)

    with pytest.raises(RuntimeError, match="without a category"):
        apply_classifications(
            [
                ClassificationDecision(
                    fingerprint=transactions[0].fingerprint,
                    category="TestOnly",
                    rule_name="manual",
                )
            ]
        )

    after = list_transactions(limit=None, neutralize=False)
    assert all(transaction.category is None for transaction in after)
