"""Tests for vault module."""

import pytest
from pathlib import Path

from penny.vault import (
    VaultConfig,
    LogManager,
    InitManifest,
    AccountCreatedManifest,
    IngestManifest,
    RulesManifest,
)


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

    def test_log_dir(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        assert config.log_dir == tmp_path / "vault" / "log"

    def test_initialize_creates_structure(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        assert not config.exists()
        assert not config.is_initialized()

        config.initialize()

        assert config.exists()
        assert config.is_initialized()
        assert config.log_dir.exists()


class TestManifests:
    def test_init_manifest_roundtrip(self):
        manifest = InitManifest(app_version="0.1.0")
        json_str = manifest.to_json()
        loaded = InitManifest.from_json(json_str)

        assert loaded.type == "init"
        assert loaded.app_version == "0.1.0"
        assert loaded.schema_version == 1

    def test_account_created_manifest(self):
        manifest = AccountCreatedManifest(
            bank="comdirect",
            bank_account_number="12345678",
            display_name="Main Account",
            iban="DE89370400440532013000",
        )

        data = manifest.to_dict()
        assert data["type"] == "account_created"
        assert data["bank"] == "comdirect"
        assert data["iban"] == "DE89370400440532013000"

    def test_ingest_manifest(self):
        manifest = IngestManifest(
            csv_files=["export.csv", "export2.csv"],
            parser="comdirect",
            parser_version="comdirect@1",
            app_version="0.1.0",
            status="applied",
        )

        data = manifest.to_dict()
        assert data["type"] == "ingest"
        assert data["csv_files"] == ["export.csv", "export2.csv"]
        assert data["parser_version"] == "comdirect@1"

    def test_manifest_write_read(self, tmp_path):
        manifest = InitManifest(app_version="0.1.0")
        path = tmp_path / "manifest.json"

        manifest.write(path)
        loaded = InitManifest.read(path)

        assert loaded.type == "init"
        assert loaded.app_version == "0.1.0"


class TestLogManager:
    @pytest.fixture
    def vault(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        config.initialize()
        return LogManager(config)

    def test_empty_vault(self, vault):
        assert vault.count() == 0
        assert vault.list_entries() == []
        assert vault.latest_entry() is None
        assert vault.next_sequence() == 1

    def test_append_simple_entry(self, vault):
        manifest = InitManifest(app_version="0.1.0")
        entry = vault.append("init", manifest)

        assert entry.sequence == 1
        assert entry.entry_type == "init"
        assert entry.path.exists()
        assert entry.manifest_path.exists()

        # Verify manifest content
        loaded = entry.read_manifest()
        assert loaded.type == "init"
        assert loaded.app_version == "0.1.0"

    def test_append_increments_sequence(self, vault):
        vault.append("init", InitManifest(app_version="0.1.0"))
        vault.append("account_created", AccountCreatedManifest(bank="comdirect"))
        vault.append("account_created", AccountCreatedManifest(bank="sparkasse"))

        assert vault.count() == 3
        assert vault.next_sequence() == 4

        entries = vault.list_entries()
        assert [e.sequence for e in entries] == [1, 2, 3]

    def test_append_with_content_files(self, vault, tmp_path):
        # Create source CSV
        csv_content = "col1;col2\nval1;val2\n"
        csv_file = tmp_path / "export.csv"
        csv_file.write_text(csv_content)

        manifest = IngestManifest(
            csv_files=["export.csv"],
            parser="comdirect",
            parser_version="comdirect@1",
            app_version="0.1.0",
        )

        entry = vault.append("ingest_comdirect", manifest, content_files=[csv_file])

        assert entry.entry_type == "ingest_comdirect"

        # Verify CSV was copied
        copied_csv = entry.path / "export.csv"
        assert copied_csv.exists()
        assert copied_csv.read_text() == csv_content

        # Verify content_files() method
        content = entry.content_files()
        assert len(content) == 1
        assert content[0].name == "export.csv"

    def test_append_with_inline_content(self, vault):
        manifest = RulesManifest(app_version="0.1.0")
        rules_code = "from penny.classify import rule\n\n@rule('Food')\ndef food(tx): ..."

        entry = vault.append_with_content(
            "rules",
            manifest,
            content={"rules.py": rules_code},
        )

        rules_file = entry.path / "rules.py"
        assert rules_file.exists()
        assert rules_file.read_text() == rules_code

    def test_list_entries_sorted(self, vault):
        vault.append("init", InitManifest(app_version="0.1.0"))
        vault.append("account_created", AccountCreatedManifest(bank="b"))
        vault.append("account_created", AccountCreatedManifest(bank="a"))

        entries = vault.list_entries()
        sequences = [e.sequence for e in entries]
        assert sequences == [1, 2, 3]  # Sorted by sequence

    def test_get_entry_by_sequence(self, vault):
        vault.append("init", InitManifest(app_version="0.1.0"))
        vault.append("account_created", AccountCreatedManifest(bank="test"))

        entry = vault.get_entry(2)
        assert entry is not None
        assert entry.entry_type == "account_created"

        assert vault.get_entry(99) is None

    def test_latest_entry(self, vault):
        vault.append("init", InitManifest(app_version="0.1.0"))
        vault.append("account_created", AccountCreatedManifest(bank="test"))

        latest = vault.latest_entry()
        assert latest.sequence == 2
        assert latest.entry_type == "account_created"

    def test_latest_of_type(self, vault):
        vault.append("init", InitManifest(app_version="0.1.0"))
        vault.append("rules", RulesManifest(app_version="0.1.0"))
        vault.append("account_created", AccountCreatedManifest(bank="test"))
        vault.append("rules", RulesManifest(app_version="0.2.0"))

        latest_rules = vault.latest_of_type("rules")
        assert latest_rules.sequence == 4

        latest_init = vault.latest_of_type("init")
        assert latest_init.sequence == 1

    def test_iter_entries(self, vault):
        vault.append("init", InitManifest(app_version="0.1.0"))
        vault.append("account_created", AccountCreatedManifest(bank="test"))

        entries = list(vault.iter_entries())
        assert len(entries) == 2
        assert entries[0].sequence == 1
        assert entries[1].sequence == 2

    def test_auto_initialize_on_append(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        vault = LogManager(config)

        assert not config.is_initialized()

        vault.append("init", InitManifest(app_version="0.1.0"))

        assert config.is_initialized()
