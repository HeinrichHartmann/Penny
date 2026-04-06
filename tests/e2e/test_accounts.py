from click.testing import CliRunner
from fastapi.testclient import TestClient

from penny.accounts import add_account
from penny.cli import main
from penny.server import app
from penny.vault import VaultConfig
from penny.vault.ledger import Ledger


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


def test_record_balance_snapshot_writes_to_ledger(fresh_runtime):
    account = add_account(
        "testbank",
        iban="DE89370400440532013000",
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/accounts/{account.id}/balance",
            json={
                "balance_cents": 12345,
                "balance_date": "2024-03-15",
                "note": "manual snapshot",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["balance_cents"] == 12345
    assert payload["balance_date"] == "2024-03-15"
    assert payload["balance_snapshot_count"] == 1

    # Balance snapshots are now written to the ledger (history.tsv)
    config = VaultConfig(fresh_runtime.vault_dir)
    ledger = Ledger(config.path)
    entries = ledger.read_entries()
    balance_entries = [e for e in entries if e.entry_type == "balance"]
    assert len(balance_entries) == 1

    balance_entry = balance_entries[0]
    snapshots = balance_entry.record.get("snapshots", [])
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot["snapshot_date"] == "2024-03-15"
    assert snapshot["balance_cents"] == 12345
    assert snapshot["note"] == "manual snapshot"
