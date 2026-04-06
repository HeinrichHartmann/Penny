"""Tests for vault module."""

from pathlib import Path

import pytest

from penny.vault import (
    VaultConfig,
    ensure_rules_snapshot,
    save_rules_snapshot,
)
from penny.vault.ledger import Ledger, LedgerEntry


class TestVaultConfig:
    def test_default_path(self, monkeypatch):
        monkeypatch.delenv("PENNY_VAULT_DIR", raising=False)
        config = VaultConfig()
        assert config.path == Path.home() / "Documents" / "Penny"

    def test_env_var_override(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PENNY_VAULT_DIR", str(tmp_path / "custom"))
        config = VaultConfig()
        assert config.path == tmp_path / "custom"

    def test_explicit_path(self, tmp_path):
        config = VaultConfig(tmp_path / "explicit")
        assert config.path == tmp_path / "explicit"

    def test_initialize_creates_structure(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        assert not config.exists()
        assert not config.is_initialized()

        config.initialize()

        assert config.exists()
        assert config.is_initialized()
        assert (config.path / "transactions").exists()
        assert config.rules_dir.exists()
        assert (config.path / "balance").exists()
        assert (config.path / "history.tsv").exists()


class TestLedger:
    @pytest.fixture
    def ledger(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        config.initialize()
        return Ledger(config.path)

    def test_empty_ledger(self, ledger):
        assert len(ledger.read_entries()) == 0
        assert ledger.next_sequence() == 1

    def test_append_entry(self, ledger):
        entry = LedgerEntry(
            sequence=1,
            entry_type="ingest",
            enabled=True,
            timestamp="2024-04-05T10:00:00Z",
            record={
                "csv_files": ["export.csv"],
                "parser": "comdirect",
                "parser_version": "comdirect@1",
                "app_version": "0.1.0",
            },
        )

        ledger.append_entry(entry)

        entries = ledger.read_entries()
        assert len(entries) == 1
        assert entries[0].sequence == 1
        assert entries[0].entry_type == "ingest"
        assert entries[0].record["parser"] == "comdirect"

    def test_list_entries_sorted(self, ledger):
        for i in range(1, 4):
            entry = LedgerEntry(
                sequence=i,
                entry_type="ingest",
                enabled=True,
                timestamp=f"2024-04-05T10:{i:02d}:00Z",
                record={"csv_files": ["a.csv"], "parser": "comdirect"},
            )
            ledger.append_entry(entry)

        entries = ledger.read_entries()
        sequences = [e.sequence for e in entries]
        assert sequences == [1, 2, 3]

    def test_get_entry_by_sequence(self, ledger):
        ledger.append_entry(
            LedgerEntry(1, "ingest", True, "2024-04-05T10:00:00Z", {"parser": "comdirect"})
        )
        ledger.append_entry(
            LedgerEntry(2, "ingest", True, "2024-04-05T10:01:00Z", {"parser": "comdirect"})
        )

        entry = ledger.get_entry(2)
        assert entry is not None
        assert entry.sequence == 2

        assert ledger.get_entry(99) is None

    def test_update_enabled_flag(self, ledger):
        ledger.append_entry(
            LedgerEntry(1, "ingest", True, "2024-04-05T10:00:00Z", {"parser": "comdirect"})
        )
        ledger.append_entry(
            LedgerEntry(2, "ingest", True, "2024-04-05T10:01:00Z", {"parser": "comdirect"})
        )

        ledger.update_enabled(1, False)

        entries = ledger.read_entries()
        assert entries[0].enabled is False
        assert entries[1].enabled is True


class TestRulesStore:
    def test_ensure_rules_snapshot_creates_default(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        path = ensure_rules_snapshot(config)

        assert path.exists()
        assert path.parent == config.rules_dir
        assert path.name.endswith("_rules.py")

    def test_save_rules_snapshot_appends_to_ledger(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        path = save_rules_snapshot("DEFAULT_CATEGORY = 'x'\n", config)
        ledger = Ledger(config.path)
        entries = ledger.read_entries()

        assert path.exists()
        assert len(entries) == 1
        assert entries[0].entry_type == "rules"
        assert path.name == entries[0].record["filename"]

    def test_save_rules_snapshot_updates_current_rules_copy(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))

        config = VaultConfig(tmp_path / "vault")
        save_rules_snapshot("DEFAULT_CATEGORY = 'x'\n", config)
        save_rules_snapshot("DEFAULT_CATEGORY = 'y'\n", config)

        current_rules_path = home / "Penny" / "rules.py"
        assert current_rules_path.exists()
        assert current_rules_path.read_text(encoding="utf-8") == "DEFAULT_CATEGORY = 'y'\n"
        assert list(current_rules_path.parent.glob(".rules.py.tmp.*")) == []
