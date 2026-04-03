from click.testing import CliRunner

from penny.cli import main


def test_add_account_assigns_sequential_id(registry):
    a1 = registry.add("comdirect")
    a2 = registry.add("sparkasse")

    assert a1.id == 1
    assert a2.id == 2


def test_add_with_account_number(registry):
    account = registry.add("comdirect", bank_account_number="9788862492")

    assert "9788862492" in account.bank_account_numbers


def test_find_by_account_number(registry):
    registry.add("comdirect", bank_account_number="9788862492")

    found = registry.find_by_bank_account_number("comdirect", "9788862492")

    assert found is not None
    assert found.bank == "comdirect"


def test_remove_soft_deletes(registry):
    account = registry.add("comdirect")

    registry.remove(account.id)

    assert registry.get(account.id).hidden is True
    assert len(registry.list()) == 0
    assert len(registry.list(include_hidden=True)) == 1


def test_add_duplicate_hidden_account_fails(registry):
    account = registry.add("comdirect", bank_account_number="9788862492")
    registry.remove(account.id)

    try:
        registry.add("comdirect", bank_account_number="9788862492")
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("Expected duplicate account creation to fail")


def test_accounts_cli_add_list_remove(monkeypatch, tmp_path):
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
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
