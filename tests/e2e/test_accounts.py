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


def test_disabling_balance_snapshot_persists_across_rebuild(fresh_runtime):
    account = add_account(
        "testbank",
        iban="DE89370400440532013000",
    )

    with TestClient(app) as client:
        create_response = client.post(
            f"/api/accounts/{account.id}/balance",
            json={
                "balance_cents": 12345,
                "balance_date": "2024-03-15",
                "note": "manual snapshot",
            },
        )
        assert create_response.status_code == 200

        history_response = client.get("/api/imports")
        assert history_response.status_code == 200
        balance_entries = [
            entry
            for entry in history_response.json()["imports"]
            if entry["type"] == "balance_anchors"
        ]
        assert len(balance_entries) == 1
        sequence = balance_entries[0]["sequence"]
        assert balance_entries[0]["enabled"] is True

        value_history_response = client.get(f"/api/account_value_history?accounts={account.id}")
        assert value_history_response.status_code == 200
        assert len(value_history_response.json()["balance_snapshots"]) == 1

        toggle_response = client.post(f"/api/imports/{sequence}/toggle")
        assert toggle_response.status_code == 200
        assert toggle_response.json() == {"sequence": sequence, "enabled": False}

        accounts_response = client.get("/api/accounts")
        assert accounts_response.status_code == 200
        accounts = accounts_response.json()["accounts"]
        assert len(accounts) == 1
        assert accounts[0]["balance_snapshot_count"] == 0

        value_history_response = client.get(f"/api/account_value_history?accounts={account.id}")
        assert value_history_response.status_code == 200
        assert value_history_response.json()["balance_snapshots"] == []

        rebuild_response = client.post("/api/rebuild")
        assert rebuild_response.status_code == 200

        history_after_rebuild = client.get("/api/imports")
        assert history_after_rebuild.status_code == 200
        balance_entries_after_rebuild = [
            entry
            for entry in history_after_rebuild.json()["imports"]
            if entry["type"] == "balance_anchors"
        ]
        assert len(balance_entries_after_rebuild) == 1
        assert balance_entries_after_rebuild[0]["enabled"] is False

        accounts_after_rebuild = client.get("/api/accounts")
        assert accounts_after_rebuild.status_code == 200
        rebuilt_accounts = accounts_after_rebuild.json()["accounts"]
        assert len(rebuilt_accounts) == 1
        assert rebuilt_accounts[0]["balance_snapshot_count"] == 0
        assert rebuilt_accounts[0]["balance_cents"] is None
        assert rebuilt_accounts[0]["balance_date"] is None

        value_history_after_rebuild = client.get(
            f"/api/account_value_history?accounts={account.id}"
        )
        assert value_history_after_rebuild.status_code == 200
        assert value_history_after_rebuild.json()["balance_snapshots"] == []
