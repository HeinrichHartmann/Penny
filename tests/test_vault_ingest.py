"""Tests for vault ingest flow."""

import pytest
from pathlib import Path

from penny.vault import (
    VaultConfig,
    LogManager,
    ingest_csv,
    IngestRequest,
)
from penny.ingest import read_file_with_encoding


class TestVaultIngest:
    @pytest.fixture
    def vault_config(self, tmp_path, monkeypatch):
        """Create a vault config pointing to tmp_path."""
        vault_path = tmp_path / "vault"
        monkeypatch.setenv("PENNY_VAULT_DIR", str(vault_path))
        monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
        return VaultConfig(vault_path)

    def test_ingest_creates_log_entry(self, vault_config, fixture_dir):
        """Ingest should create a log entry with manifest and CSV."""
        csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
        content = read_file_with_encoding(csv_path)

        request = IngestRequest(
            filename=csv_path.name,
            content=content,
        )

        result = ingest_csv(request, config=vault_config)

        # Check result
        assert result.account_bank == "comdirect"
        assert result.transactions_total == 3
        assert result.transactions_new == 3
        assert result.transactions_duplicate == 0

        # Check log entry was created
        log = LogManager(vault_config)
        assert log.count() == 1

        entry = log.latest_entry()
        assert entry.entry_type == "ingest_comdirect"

        # Check manifest
        manifest = entry.read_manifest()
        assert manifest.type == "ingest"
        assert manifest.parser == "comdirect"
        assert manifest.csv_files == [csv_path.name]

        # Check CSV was copied
        copied_csv = entry.path / csv_path.name
        assert copied_csv.exists()
        assert copied_csv.read_text() == content

    def test_ingest_deduplicates_on_reimport(self, vault_config, fixture_dir):
        """Re-importing same CSV should create new entry but deduplicate transactions."""
        csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
        content = read_file_with_encoding(csv_path)

        request = IngestRequest(filename=csv_path.name, content=content)

        # First import
        result1 = ingest_csv(request, config=vault_config)
        assert result1.transactions_new == 3
        assert result1.transactions_duplicate == 0

        # Second import - same file
        result2 = ingest_csv(request, config=vault_config)
        assert result2.transactions_new == 0
        assert result2.transactions_duplicate == 3

        # Should have 2 log entries
        log = LogManager(vault_config)
        assert log.count() == 2

    def test_ingest_sparkasse(self, vault_config, fixture_dir):
        """Test ingesting Sparkasse CAMT V8 format."""
        csv_path = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"
        content = read_file_with_encoding(csv_path)

        request = IngestRequest(filename=csv_path.name, content=content)
        result = ingest_csv(request, config=vault_config)

        assert result.account_bank == "sparkasse"
        assert result.parser_name == "Sparkasse"
        assert result.transactions_total == 3

        # Check log entry
        log = LogManager(vault_config)
        entry = log.latest_entry()
        assert entry.entry_type == "ingest_sparkasse"
