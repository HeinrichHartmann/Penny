from datetime import date

from click.testing import CliRunner

from penny.accounts import add_account
from penny.cli import main
from penny.transactions import (
    Transaction,
    generate_fingerprint,
    list_transactions,
    store_transactions,
)
from penny.vault import (
    VaultConfig,
    ensure_vault_initialized,
    latest_rules_path,
    save_rules_snapshot,
)


def _make_tx(account_id: int, payee: str, amount_cents: int, **kwargs) -> Transaction:
    tx_date = kwargs.pop("tx_date", date(2026, 9, 1))
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
        raw_buchungstext=payee,
        raw_row={},
        **kwargs,
    )


def _seed_data():
    """Create an account with a few transactions and a base rules file."""
    config = VaultConfig()
    ensure_vault_initialized(config)
    save_rules_snapshot(
        "from penny.classify import rule\n\nDEFAULT_CATEGORY = 'uncategorized'\n",
        config,
    )
    acc = add_account("testbank", display_name="HartmannIT")
    txs = [
        _make_tx(acc.id, "STRIPE", 70000),
        _make_tx(acc.id, "Venue Invoice", -2500000, category="uncategorized"),
        _make_tx(acc.id, "Langfuse Sponsoring", 892500, category="uncategorized"),
    ]
    store_transactions(txs)
    return acc, txs


# -- penny transactions list --------------------------------------------------


def test_transactions_list_account_by_name():
    acc, _txs = _seed_data()
    runner = CliRunner()
    result = runner.invoke(main, ["transactions", "list", "-a", "HartmannIT"])

    assert result.exit_code == 0
    assert "STRIPE" in result.output
    assert "Venue Invoice" in result.output


def test_transactions_list_account_by_name_case_insensitive():
    _seed_data()
    runner = CliRunner()
    result = runner.invoke(main, ["transactions", "list", "-a", "hartmannit"])

    assert result.exit_code == 0
    assert "STRIPE" in result.output


def test_transactions_list_account_unknown_name():
    _seed_data()
    runner = CliRunner()
    result = runner.invoke(main, ["transactions", "list", "-a", "NoSuchAccount"])

    assert result.exit_code != 0
    assert "Unknown account" in result.output


def test_transactions_list_uncategorized():
    _seed_data()
    runner = CliRunner()
    result = runner.invoke(main, ["transactions", "list", "--uncategorized"])

    assert result.exit_code == 0
    assert "Venue Invoice" in result.output
    assert "Langfuse Sponsoring" in result.output
    # STRIPE has no category set (None), which defaults to uncategorized display
    # but the filter uses category_prefix="uncategorized"


def test_transactions_list_verbose_shows_fingerprints():
    _acc, txs = _seed_data()
    runner = CliRunner()
    result = runner.invoke(main, ["transactions", "list", "-v"])

    assert result.exit_code == 0
    assert "Fingerprint" in result.output
    # Check that actual fingerprints appear
    for tx in txs:
        assert tx.fingerprint in result.output


# -- penny classify ------------------------------------------------------------


def test_classify_sets_category():
    _acc, txs = _seed_data()
    venue_tx = txs[1]  # "Venue Invoice"

    runner = CliRunner()
    result = runner.invoke(main, ["classify", venue_tx.fingerprint, "signals/venue"])

    assert result.exit_code == 0
    assert "signals/venue" in result.output
    assert "Classified." in result.output

    # Verify DB was updated
    updated = list_transactions(limit=None, neutralize=False)
    matched = [t for t in updated if t.fingerprint == venue_tx.fingerprint]
    assert len(matched) == 1
    assert matched[0].category == "signals/venue"


def test_classify_appends_to_rules_file():
    _acc, txs = _seed_data()
    venue_tx = txs[1]

    runner = CliRunner()
    result = runner.invoke(main, ["classify", venue_tx.fingerprint, "signals/venue"])
    assert result.exit_code == 0

    # Check the latest rules snapshot contains the fingerprint rule
    config = VaultConfig()
    rules_path = latest_rules_path(config)
    assert rules_path is not None
    content = rules_path.read_text()
    assert venue_tx.fingerprint in content
    assert "signals/venue" in content


def test_classify_unknown_fingerprint():
    _seed_data()
    runner = CliRunner()
    result = runner.invoke(main, ["classify", "nonexistent_fp", "signals/venue"])

    assert result.exit_code != 0
    assert "Transaction not found" in result.output
