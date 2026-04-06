"""Tests for vault ingest flow."""

import pytest

from penny.ingest import read_file_with_encoding
from penny.transactions import count_transactions
from penny.vault import (
    IngestRequest,
    VaultConfig,
    ingest_csv,
    replay_vault,
)
from penny.vault.ingest import DuplicateImportError
from penny.vault.ledger import Ledger

pytestmark = pytest.mark.integration


class TestVaultIngest:
    @pytest.fixture
    def vault_config(self, tmp_path, monkeypatch):
        """Create a vault config pointing to tmp_path."""
        vault_path = tmp_path / "vault"
        monkeypatch.setenv("PENNY_VAULT_DIR", str(vault_path))
        monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
        return VaultConfig(vault_path)

    def test_ingest_creates_ledger_entry(self, vault_config, fixture_dir):
        """Ingest should create a ledger entry and store CSV."""
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

        # Check ledger entry was created
        ledger = Ledger(vault_config.path)
        entries = ledger.read_entries()
        assert len(entries) == 1

        entry = entries[0]
        assert entry.sequence == 1
        assert entry.entry_type == "ingest"
        assert entry.record["parser"] == "comdirect"
        assert entry.record["csv_files"] == [csv_path.name]

        # Check CSV was copied to transactions directory with PI prefix
        copied_csv = entry.get_csv_path(vault_config.path, csv_path.name)
        assert copied_csv.exists()
        assert copied_csv.name == f"PI{entry.sequence:04d}_{csv_path.name}"
        assert copied_csv.read_text() == content

    def test_ingest_rejects_duplicate_csv(self, vault_config, fixture_dir):
        """Re-importing same CSV should be rejected at the content level."""
        csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
        content = read_file_with_encoding(csv_path)

        request = IngestRequest(filename=csv_path.name, content=content)

        # First import
        result1 = ingest_csv(request, config=vault_config)
        assert result1.transactions_new == 3
        assert result1.transactions_duplicate == 0

        # Second import - same file should be rejected
        with pytest.raises(DuplicateImportError) as exc_info:
            ingest_csv(request, config=vault_config)
        assert exc_info.value.existing_sequence == 1

        # Should still have only 1 ledger entry
        ledger = Ledger(vault_config.path)
        assert len(ledger.read_entries()) == 1

    def test_ingest_sparkasse(self, vault_config, fixture_dir):
        """Test ingesting Sparkasse CAMT V8 format."""
        csv_path = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"
        content = read_file_with_encoding(csv_path)

        request = IngestRequest(filename=csv_path.name, content=content)
        result = ingest_csv(request, config=vault_config)

        assert result.account_bank == "sparkasse"
        assert result.parser_name == "Sparkasse"
        assert result.transactions_total == 3

        # Check ledger entry
        ledger = Ledger(vault_config.path)
        entries = ledger.read_entries()
        assert len(entries) == 1
        assert entries[0].entry_type == "ingest"
        assert entries[0].record["parser"] == "sparkasse"

    def test_ingest_normalizes_prefixed_uploaded_filename(self, vault_config, fixture_dir):
        """PI-prefixed vault filenames should be normalized before parser detection and storage."""
        csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
        prefixed_name = f"PI01231231_{csv_path.name}"

        request = IngestRequest(
            filename=prefixed_name,
            content=csv_path.read_bytes(),
        )

        result = ingest_csv(request, config=vault_config)

        assert result.account_bank == "comdirect"
        assert result.transactions_total == 3

        ledger = Ledger(vault_config.path)
        entries = ledger.read_entries()
        assert len(entries) == 1

        entry = entries[0]
        assert entry.record["csv_files"] == [csv_path.name]

        copied_csv = entry.get_csv_path(vault_config.path, csv_path.name)
        assert copied_csv.exists()
        assert copied_csv.name == f"PI{entry.sequence:04d}_{csv_path.name}"


class TestVaultReplay:
    @pytest.fixture
    def vault_config(self, tmp_path, monkeypatch):
        """Create a vault config pointing to tmp_path."""
        vault_path = tmp_path / "vault"
        monkeypatch.setenv("PENNY_VAULT_DIR", str(vault_path))
        monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
        return VaultConfig(vault_path)

    def test_replay_restores_data_after_db_reset(self, vault_config, fixture_dir):
        """Ingest -> nuke DB -> replay -> data restored."""
        from penny.db import init_db

        csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
        content = read_file_with_encoding(csv_path)

        # 1. Ingest CSV (writes to vault + DB)
        request = IngestRequest(filename=csv_path.name, content=content)
        result = ingest_csv(request, config=vault_config)
        assert result.transactions_new == 3
        assert count_transactions() == 3

        # 2. Nuke DB by reinitializing
        init_db()  # Creates fresh in-memory DB
        assert count_transactions() == 0

        # 3. Replay from vault
        replay_result = replay_vault(vault_config)
        assert replay_result.entries_processed == 1
        assert replay_result.entries_by_type == {"ingest": 1}

        # 4. Verify transactions are back
        assert count_transactions() == 3

    def test_replay_multiple_ingests(self, vault_config, fixture_dir):
        """Multiple ingests replay correctly."""
        from penny.db import init_db

        # Ingest two different files
        csv1 = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
        csv2 = fixture_dir / "20260401-12345678-umsatz-camt52v8.CSV"

        request1 = IngestRequest(filename=csv1.name, content=read_file_with_encoding(csv1))
        request2 = IngestRequest(filename=csv2.name, content=read_file_with_encoding(csv2))

        ingest_csv(request1, config=vault_config)
        ingest_csv(request2, config=vault_config)

        # Should have 6 transactions (3 + 3)
        assert count_transactions() == 6

        # Nuke and replay
        init_db()
        assert count_transactions() == 0

        replay_result = replay_vault(vault_config)
        assert replay_result.entries_processed == 2
        assert replay_result.entries_by_type == {"ingest": 2}
        assert count_transactions() == 6

    def test_replay_is_deterministic(self, vault_config, fixture_dir):
        """Same vault replays to same state."""
        from penny.db import init_db
        from penny.transactions import list_transactions

        csv_path = fixture_dir / "umsaetze_9788862492_20260331-1354.csv"
        request = IngestRequest(
            filename=csv_path.name,
            content=read_file_with_encoding(csv_path),
        )
        ingest_csv(request, config=vault_config)

        # First replay
        init_db()
        replay_vault(vault_config)
        txs1 = list_transactions(limit=None, neutralize=False)
        fingerprints1 = sorted(tx.fingerprint for tx in txs1)

        # Second replay
        init_db()
        replay_vault(vault_config)
        txs2 = list_transactions(limit=None, neutralize=False)
        fingerprints2 = sorted(tx.fingerprint for tx in txs2)

        # Same transactions with same fingerprints
        assert fingerprints1 == fingerprints2
        assert len(fingerprints1) == 3


class TestVaultMutations:
    """Tests for account operations via mutation log."""

    @pytest.fixture
    def vault_config(self, tmp_path, monkeypatch):
        """Create a vault config pointing to tmp_path."""
        vault_path = tmp_path / "vault"
        monkeypatch.setenv("PENNY_VAULT_DIR", str(vault_path))
        monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
        config = VaultConfig(vault_path)
        config.initialize()
        return config

    def test_account_mutations_replay(self, vault_config):
        """Account operations via mutations should be replayed."""
        from penny.accounts import add_account, get_account, update_account_metadata
        from penny.db import init_db

        # Create initial database and account
        init_db()
        account = add_account("testbank", bank_account_number="123456")
        account_id = account.id

        # Update account metadata (this writes to ledger as mutation entry)
        update_account_metadata(
            account_id,
            display_name="My Account",
            iban="DE1234567890",
            holder="John Doe",
            notes="Test notes",
        )

        # Verify update worked
        updated = get_account(account_id)
        assert updated is not None
        assert updated.display_name == "My Account"

        # Check ledger has mutation entries
        ledger = Ledger(vault_config.path)
        entries = ledger.read_entries()
        mutation_entries = [e for e in entries if e.entry_type == "mutation"]
        assert len(mutation_entries) >= 2  # account_created + account_updated

        # Nuke DB and replay from vault
        init_db()
        replay_result = replay_vault(vault_config)
        # Mutations are replayed
        assert "mutation" in replay_result.entries_by_type
        assert replay_result.entries_by_type["mutation"] >= 2

        # Verify account metadata was restored
        restored = get_account(account_id)
        assert restored is not None
        assert restored.display_name == "My Account"
        assert restored.iban == "DE1234567890"
