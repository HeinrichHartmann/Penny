from penny.accounts import (
    add_account,
    find_account_by_bank_account_number,
    get_account,
    list_accounts,
    remove_account,
)
from penny.vault import VaultConfig
from penny.vault.ledger import Ledger


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


def test_account_writes_append_mutations(db):
    account = add_account("comdirect", bank_account_number="9788862492")
    remove_account(account.id)

    config = VaultConfig()
    entries = Ledger(config.path).read_entries()
    mutation_entries = [e for e in entries if e.entry_type == "mutation"]
    assert [e.record["mutation_type"] for e in mutation_entries] == ["account_created", "account_hidden"]
