"""Tests for simple ledger-based vault storage (ADR-012)."""

import pytest

from penny.vault.ledger import Ledger, LedgerEntry


class TestLedgerEntry:
    """Test LedgerEntry serialization."""

    def test_ingest_entry_roundtrip(self):
        """Test ingest entry serialization."""
        entry = LedgerEntry(
            sequence=1,
            entry_type="ingest",
            enabled=True,
            timestamp="2024-04-05T10:00:00Z",
            record={"parser": "sparkasse", "csv_files": ["file.CSV"]},
        )

        line = entry.to_tsv_line()
        assert (
            line
            == '0001\tingest\t1\t2024-04-05T10:00:00Z\t{"parser":"sparkasse","csv_files":["file.CSV"]}'
        )

        restored = LedgerEntry.from_tsv_line(line)
        assert restored.sequence == 1
        assert restored.entry_type == "ingest"
        assert restored.enabled is True
        assert restored.record["parser"] == "sparkasse"

    def test_rules_entry(self):
        """Test rules entry."""
        entry = LedgerEntry(
            sequence=2,
            entry_type="rules",
            enabled=True,
            timestamp="2024-04-05T10:01:00Z",
            record={"filename": "demo_rules.py"},
        )

        line = entry.to_tsv_line()
        restored = LedgerEntry.from_tsv_line(line)
        assert restored.entry_type == "rules"
        assert restored.record["filename"] == "demo_rules.py"

    def test_balance_entry_disabled(self):
        """Test balance entry with enabled=False."""
        entry = LedgerEntry(
            sequence=3,
            entry_type="balance",
            enabled=False,
            timestamp="2024-04-05T10:02:00Z",
            record={"filename": "balance.tsv", "count": 5},
        )

        line = entry.to_tsv_line()
        assert "\t0\t" in line  # enabled=0

        restored = LedgerEntry.from_tsv_line(line)
        assert restored.enabled is False

    def test_invalid_line_raises(self):
        """Test invalid TSV line raises ValueError."""
        with pytest.raises(ValueError, match="expected 5 columns"):
            LedgerEntry.from_tsv_line("invalid")

    def test_get_file_paths(self, tmp_path):
        """Test file path generation."""
        # Ingest entry - CSVs stored flat with PI prefix
        ingest = LedgerEntry(
            sequence=1,
            entry_type="ingest",
            enabled=True,
            timestamp="2024-04-05T10:00:00Z",
            record={"parser": "sparkasse", "csv_files": ["file.CSV"]},
        )
        assert ingest.get_directory(tmp_path) == tmp_path / "transactions"
        assert ingest.get_file_path(tmp_path) == tmp_path / "transactions"
        assert ingest.get_csv_path(tmp_path, "file.CSV") == tmp_path / "transactions" / "PI0001_file.CSV"

        # Rules entry
        rules = LedgerEntry(
            sequence=2,
            entry_type="rules",
            enabled=True,
            timestamp="2024-04-05T10:01:00Z",
            record={"filename": "rules.py"},
        )
        assert (
            rules.get_file_path(tmp_path)
            == tmp_path / "rules" / "0002_2024-04-05T10:01:00Z_rules.py"
        )

        # Balance entry
        balance = LedgerEntry(
            sequence=3,
            entry_type="balance",
            enabled=True,
            timestamp="2024-04-05T10:02:00Z",
            record={"filename": "balance.tsv"},
        )
        assert (
            balance.get_file_path(tmp_path)
            == tmp_path / "balance" / "0003_2024-04-05T10:02:00Z_balance.tsv"
        )


class TestLedger:
    """Test Ledger class."""

    def test_empty_ledger(self, tmp_path):
        """Test empty ledger."""
        ledger = Ledger(tmp_path)
        assert ledger.read_entries() == []
        assert ledger.next_sequence() == 1

    def test_append_entry(self, tmp_path):
        """Test appending entries."""
        ledger = Ledger(tmp_path)

        entry = LedgerEntry(
            sequence=1,
            entry_type="ingest",
            enabled=True,
            timestamp="2024-04-05T10:00:00Z",
            record={"parser": "sparkasse"},
        )

        ledger.append_entry(entry)

        # Verify file exists
        assert (tmp_path / "history.tsv").exists()

        # Read back
        entries = ledger.read_entries()
        assert len(entries) == 1
        assert entries[0].sequence == 1

    def test_append_multiple_entries(self, tmp_path):
        """Test multiple entries."""
        ledger = Ledger(tmp_path)

        ledger.append_entry(
            LedgerEntry(1, "ingest", True, "2024-04-05T10:00:00Z", {"parser": "sparkasse"})
        )
        ledger.append_entry(
            LedgerEntry(2, "rules", True, "2024-04-05T10:01:00Z", {"filename": "rules.py"})
        )
        ledger.append_entry(LedgerEntry(3, "balance", False, "2024-04-05T10:02:00Z", {"count": 5}))

        entries = ledger.read_entries()
        assert len(entries) == 3
        assert entries[0].entry_type == "ingest"
        assert entries[1].entry_type == "rules"
        assert entries[2].entry_type == "balance"
        assert entries[2].enabled is False

    def test_next_sequence(self, tmp_path):
        """Test sequence number calculation."""
        ledger = Ledger(tmp_path)

        assert ledger.next_sequence() == 1

        ledger.append_entry(LedgerEntry(1, "ingest", True, "2024-04-05T10:00:00Z", {}))
        assert ledger.next_sequence() == 2

        # Gaps are fine
        ledger.append_entry(LedgerEntry(5, "rules", True, "2024-04-05T10:01:00Z", {}))
        assert ledger.next_sequence() == 6

    def test_get_entry(self, tmp_path):
        """Test getting entry by sequence."""
        ledger = Ledger(tmp_path)

        ledger.append_entry(LedgerEntry(1, "ingest", True, "2024-04-05T10:00:00Z", {}))
        ledger.append_entry(LedgerEntry(3, "rules", True, "2024-04-05T10:01:00Z", {}))

        entry = ledger.get_entry(3)
        assert entry is not None
        assert entry.entry_type == "rules"

        assert ledger.get_entry(2) is None

    def test_update_enabled(self, tmp_path):
        """Test updating enabled flag."""
        ledger = Ledger(tmp_path)

        ledger.append_entry(LedgerEntry(1, "ingest", True, "2024-04-05T10:00:00Z", {}))
        ledger.append_entry(LedgerEntry(2, "rules", True, "2024-04-05T10:01:00Z", {}))

        # Disable entry 1
        ledger.update_enabled(1, False)

        entries = ledger.read_entries()
        assert entries[0].enabled is False
        assert entries[1].enabled is True

        # Re-enable it
        ledger.update_enabled(1, True)
        entries = ledger.read_entries()
        assert entries[0].enabled is True

    def test_update_nonexistent_raises(self, tmp_path):
        """Test updating nonexistent entry raises ValueError."""
        ledger = Ledger(tmp_path)

        with pytest.raises(ValueError, match="not found"):
            ledger.update_enabled(999, False)

    def test_ledger_file_format(self, tmp_path):
        """Test history.tsv file format."""
        ledger = Ledger(tmp_path)

        ledger.append_entry(
            LedgerEntry(1, "ingest", True, "2024-04-05T10:00:00Z", {"test": "data"})
        )

        content = (tmp_path / "history.tsv").read_text()
        lines = content.strip().split("\n")

        assert lines[0] == "seq\ttype\tenabled\ttimestamp\trecord"
        assert lines[1].startswith("0001\tingest\t1\t")
