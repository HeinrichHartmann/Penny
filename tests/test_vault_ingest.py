"""Tests for vault ingest flow."""

import pytest

from penny.ingest import read_file_with_encoding
from penny.transactions import count_transactions
from penny.vault import (
    IngestRequest,
    LogManager,
    VaultConfig,
    ingest_csv,
    replay_vault,
)

pytestmark = pytest.mark.integration


class TestVaultIngest:
    @pytest.fixture
    def vault_config(self, tmp_path, monkeypatch):
        """Create a vault config pointing to tmp_path."""
        vault_path = tmp_path / "vault"
        monkeypatch.setenv("PENNY_VAULT_DIR", str(vault_path))
        monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
        return VaultConfig(vault_path)

    def test_ingest_creates_log_entry(self, vault_config, fixture_dir):
        """Ingest should create an archived import with manifest and CSV."""
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
        assert entry is not None
        assert entry.path.name.startswith("000001-")

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
        assert entry is not None
        assert entry.path.name.startswith("000001-")


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


class TestVaultAccountMutations:
    """Tests for account metadata updates and balance snapshots via vault."""

    @pytest.fixture
    def vault_config(self, tmp_path, monkeypatch):
        """Create a vault config pointing to tmp_path."""
        vault_path = tmp_path / "vault"
        monkeypatch.setenv("PENNY_VAULT_DIR", str(vault_path))
        monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path))
        config = VaultConfig(vault_path)
        config.initialize()
        return config

    def test_account_updated_applies_on_replay(self, vault_config):
        """Account metadata updates should be replayed from vault."""
        from penny.accounts import add_account, get_account, update_account_metadata
        from penny.db import init_db
        from penny.vault.manifests import AccountCreatedManifest, AccountUpdatedManifest

        # Create initial database and account
        init_db()
        account = add_account("testbank", bank_account_number="123456")
        account_id = account.id

        # Create vault log entry for account creation
        log = LogManager(vault_config)
        create_manifest = AccountCreatedManifest(
            bank="testbank",
            bank_account_number="123456",
        )
        log.append(
            entry_type="account_created",
            manifest=create_manifest,
            content_files=None,
        )

        # Update account metadata
        update_account_metadata(
            account_id,
            display_name="My Account",
            iban="DE1234567890",
            holder="John Doe",
            notes="Test notes",
        )

        # Create vault log entry for the update
        update_manifest = AccountUpdatedManifest(
            account_id=account_id,
            fields={
                "display_name": "My Account",
                "iban": "DE1234567890",
                "holder": "John Doe",
                "notes": "Test notes",
            },
        )
        log.append(
            entry_type="account_updated",
            manifest=update_manifest,
            content_files=None,
        )

        # Verify update worked
        updated = get_account(account_id)
        assert updated is not None
        assert updated.display_name == "My Account"

        # Nuke DB and replay from vault
        init_db()
        replay_result = replay_vault(vault_config)
        # Log entries + mutations are both replayed
        assert replay_result.entries_by_type["account_created"] >= 1
        assert replay_result.entries_by_type["account_updated"] >= 1

        # Verify account metadata was restored
        # Note: account_id should be the same since replay is deterministic
        restored = get_account(account_id)
        assert restored is not None
        assert restored.display_name == "My Account"
        assert restored.iban == "DE1234567890"
        assert restored.holder == "John Doe"
        assert restored.notes == "Test notes"

    def test_balance_snapshot_applies_on_replay(self, vault_config):
        """Balance snapshots should be replayed from vault."""
        from datetime import date as date_type

        from penny.accounts import add_account, get_account, update_account_balance
        from penny.db import init_db
        from penny.vault.manifests import AccountCreatedManifest, BalanceSnapshotManifest

        # Create initial database and account
        init_db()
        account = add_account("testbank", bank_account_number="123456")
        account_id = account.id

        # Create vault log entry for account creation
        log = LogManager(vault_config)
        create_manifest = AccountCreatedManifest(
            bank="testbank",
            bank_account_number="123456",
        )
        log.append(
            entry_type="account_created",
            manifest=create_manifest,
            content_files=None,
        )

        # Record balance snapshot
        snapshot_date = date_type(2024, 3, 31)
        update_account_balance(
            account_id,
            balance_cents=123456,
            balance_date=snapshot_date,
        )

        # Create vault log entry for balance snapshot
        balance_manifest = BalanceSnapshotManifest(
            account_id=account_id,
            subaccount_type="giro",
            snapshot_date=snapshot_date.isoformat(),
            balance_cents=123456,
            note="Test balance",
        )
        log.append(
            entry_type="balance_snapshot",
            manifest=balance_manifest,
            content_files=None,
        )

        # Verify balance was recorded
        updated = get_account(account_id)
        assert updated is not None
        assert updated.balance_cents == 123456

        # Nuke DB and replay from vault
        init_db()
        replay_result = replay_vault(vault_config)
        # Log entries + mutations are both replayed
        assert replay_result.entries_by_type["account_created"] >= 1
        assert replay_result.entries_by_type["balance_snapshot"] >= 1

        # Verify balance was restored
        # Note: account_id should be the same since replay is deterministic
        restored = get_account(account_id)
        assert restored is not None
        assert restored.balance_cents == 123456
        assert restored.balance_date == snapshot_date
