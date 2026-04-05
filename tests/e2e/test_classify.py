import asyncio

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from penny.api.rules import RulesUpdate, get_rules_path, run_rules, save_rules
from penny.server import app
from penny.classify import ClassificationDecision
from penny.cli import main
from penny.db import init_db
from penny.transactions import apply_classifications, list_transactions
from penny.vault import VaultConfig, replay_vault, save_rules_snapshot
from penny.vault.ledger import Ledger


def _import_fixture(runner: CliRunner, fixture_dir):
    csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
    result = runner.invoke(main, ["import", str(csv_path)])
    assert result.exit_code == 0


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

    config = VaultConfig()
    entries = Ledger(config.path).read_entries()
    mutation_entries = [e for e in entries if e.entry_type == "mutation"]
    if mutation_entries:
        assert mutation_entries[-1].record.get("mutation_type") == "rules_updated"

    init_db(None)
    replay_vault(VaultConfig())
    replayed = {
        transaction.payee: transaction.category
        for transaction in list_transactions(limit=None, neutralize=False)
    }
    assert replayed["Example Employer"] == "Income:Salary"
    assert replayed["HOTEL EXAMPLE BERLIN"] == "NeedsReview"


def test_save_rules_reclassifies_transactions_synchronously(fixture_dir):
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

    assert result_save["status"] == "saved"

    transactions = list_transactions(limit=None, neutralize=False)
    categories = {transaction.payee: transaction.category for transaction in transactions}

    assert categories["Example Employer"] == "Income:Salary"
    assert categories["HOTEL EXAMPLE BERLIN"] == "NeedsReview"
    assert categories["AMAZON PAYMENTS EUROPE S.C.A."] == "NeedsReview"


def test_import_rules_api_reclassifies_transactions_synchronously(fixture_dir):
    runner = CliRunner()
    _import_fixture(runner, fixture_dir)

    rules_content = """
from penny.classify import contains, rule

DEFAULT_CATEGORY = "NeedsReview"

@rule("Income:Salary", name="salary")
def salary(transaction):
    return contains(transaction.payee, "Employer")
""".strip() + "\n"

    with TestClient(app) as client:
        response = client.post(
            "/api/import",
            files={"file": ("rules.py", rules_content.encode("utf-8"), "text/x-python")},
        )

    assert response.status_code == 200
    assert response.json()["type"] == "rules"

    transactions = list_transactions(limit=None, neutralize=False)
    categories = {transaction.payee: transaction.category for transaction in transactions}

    assert categories["Example Employer"] == "Income:Salary"
    assert categories["HOTEL EXAMPLE BERLIN"] == "NeedsReview"
    assert categories["AMAZON PAYMENTS EUROPE S.C.A."] == "NeedsReview"


def test_apply_classifications_requires_complete_pass(fixture_dir):
    runner = CliRunner()
    _import_fixture(runner, fixture_dir)

    transactions = list_transactions(limit=None, neutralize=False)
    before = {
        transaction.fingerprint: (transaction.category, transaction.classification_rule)
        for transaction in transactions
    }

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
    after_map = {
        transaction.fingerprint: (transaction.category, transaction.classification_rule)
        for transaction in after
    }
    assert after_map == before


def test_replay_vault_fails_loudly_for_invalid_rules(fixture_dir):
    runner = CliRunner()
    _import_fixture(runner, fixture_dir)
    save_rules_snapshot("def broken(:\n")

    init_db(None)

    with pytest.raises(SyntaxError):
        replay_vault(VaultConfig())
