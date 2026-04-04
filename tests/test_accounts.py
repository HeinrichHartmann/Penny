from click.testing import CliRunner
import pytest

from penny.accounts import (
    add_account,
    find_account_by_bank_account_number,
    get_account,
    list_accounts,
    remove_account,
)
from penny.cli import main


def test_add_account_assigns_sequential_id(db):
    a1 = add_account("comdirect")
    a2 = add_account("sparkasse")

    assert a1.id == 1
    assert a2.id == 2


def test_add_with_account_number(db):
    account = add_account("comdirect", bank_account_number="9788862492")

    assert "9788862492" in account.bank_account_numbers


def test_find_by_account_number(db):
    add_account("comdirect", bank_account_number="9788862492")

    found = find_account_by_bank_account_number("comdirect", "9788862492")

    assert found is not None
    assert found.bank == "comdirect"


def test_remove_soft_deletes(db):
    account = add_account("comdirect")

    remove_account(account.id)

    assert get_account(account.id).hidden is True
    assert len(list_accounts()) == 0
    assert len(list_accounts(include_hidden=True)) == 1


def test_add_duplicate_hidden_account_fails(db):
    account = add_account("comdirect", bank_account_number="9788862492")
    remove_account(account.id)

    try:
        add_account("comdirect", bank_account_number="9788862492")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected duplicate account creation to fail")


@pytest.mark.integration
def test_accounts_cli_add_list_remove():
    runner = CliRunner()

    result = runner.invoke(main, ["accounts", "add", "comdirect", "--account-number", "9788862492"])
    assert result.exit_code == 0
    assert "Created account #1: comdirect" in result.output

    result = runner.invoke(main, ["accounts", "list"])
    assert result.exit_code == 0
    assert "comdirect" in result.output
    assert "active" in result.output

    result = runner.invoke(main, ["accounts", "remove", "1"])
    assert result.exit_code == 0
    assert "Removed account #1" in result.output

    result = runner.invoke(main, ["accounts", "list"])
    assert result.exit_code == 0
    assert "No accounts found." in result.output

    result = runner.invoke(main, ["accounts", "list", "--all"])
    assert result.exit_code == 0
    assert "hidden" in result.output
