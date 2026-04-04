"""Tests for vault module."""

import pytest
from pathlib import Path

from penny.vault import (
    VaultConfig,
    LogManager,
    IngestManifest,
    MutationLog,
    ensure_rules_snapshot,
    save_rules_snapshot,
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
        assert config.imports_dir == tmp_path / "vault" / "imports"

    def test_initialize_creates_structure(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        assert not config.exists()
        assert not config.is_initialized()

        config.initialize()

        assert config.exists()
        assert config.is_initialized()
        assert config.imports_dir.exists()
        assert config.rules_dir.exists()
        assert config.mutations_path.exists()


class TestManifests:
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
        from penny.vault import InitManifest

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

        assert entry.sequence == 1
        assert entry.path.name.startswith("000001-")

        # Verify CSV was copied
        copied_csv = entry.path / "export.csv"
        assert copied_csv.exists()
        assert copied_csv.read_text() == csv_content

        # Verify content_files() method
        content = entry.content_files()
        assert len(content) == 1
        assert content[0].name == "export.csv"

    def test_list_entries_sorted(self, vault):
        manifest = IngestManifest(csv_files=["a.csv"], parser="comdirect", parser_version="comdirect@1")
        vault.append("ingest_comdirect", manifest)
        vault.append("ingest_comdirect", manifest)
        vault.append("ingest_comdirect", manifest)

        entries = vault.list_entries()
        sequences = [e.sequence for e in entries]
        assert sequences == [1, 2, 3]  # Sorted by sequence

    def test_get_entry_by_sequence(self, vault):
        manifest = IngestManifest(csv_files=["a.csv"], parser="comdirect", parser_version="comdirect@1")
        vault.append("ingest_comdirect", manifest)
        vault.append("ingest_comdirect", manifest)

        entry = vault.get_entry(2)
        assert entry is not None
        assert entry.sequence == 2

        assert vault.get_entry(99) is None

    def test_latest_entry(self, vault):
        manifest = IngestManifest(csv_files=["a.csv"], parser="comdirect", parser_version="comdirect@1")
        vault.append("ingest_comdirect", manifest)
        vault.append("ingest_comdirect", manifest)

        latest = vault.latest_entry()
        assert latest.sequence == 2

    def test_iter_entries(self, vault):
        manifest = IngestManifest(csv_files=["a.csv"], parser="comdirect", parser_version="comdirect@1")
        vault.append("ingest_comdirect", manifest)
        vault.append("ingest_comdirect", manifest)

        entries = list(vault.iter_entries())
        assert len(entries) == 2
        assert entries[0].sequence == 1
        assert entries[1].sequence == 2


class TestMutationLog:
    def test_append_row(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        log = MutationLog(config)

        row = log.append(
            "rules_updated",
            entity_type="rules",
            payload={"path": "2026-01-01T00:00:00Z_rules.py"},
        )

        assert row.seq == 1
        assert len(log.list_rows()) == 1
        assert "rules_updated" in config.mutations_path.read_text(encoding="utf-8")


class TestRulesStore:
    def test_ensure_rules_snapshot_creates_default(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        path = ensure_rules_snapshot(config)

        assert path.exists()
        assert path.parent == config.rules_dir
        assert path.name.endswith("_rules.py")

    def test_save_rules_snapshot_appends_mutation(self, tmp_path):
        config = VaultConfig(tmp_path / "vault")
        path = save_rules_snapshot("DEFAULT_CATEGORY = 'x'\n", config)
        rows = MutationLog(config).list_rows()

        assert path.exists()
        assert rows[-1].type == "rules_updated"
        assert path.name in rows[-1].payload_json
