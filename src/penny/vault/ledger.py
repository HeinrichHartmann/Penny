"""Ledger-based vault storage with history.tsv (ADR-012).

Simple TSV format:
    seq	type	enabled	timestamp	record
    0001	ingest	1	2024-04-05T10:00:00Z	{"parser":"sparkasse","csv_files":["file.CSV"]}
    0002	rules	1	2024-04-05T10:01:00Z	{"filename":"rules.py"}
    0003	balance	0	2024-04-05T10:02:00Z	{"filename":"balance.tsv","count":5}

File structure:
    ~/Documents/Penny/
        history.tsv
        rules/0002_2024-04-05T10:01:00Z_rules.py
        balance/0003_2024-04-05T10:02:00Z_balance.tsv
        transactions/0001_2024-04-05T10:00:00Z/file.CSV
        transactions/0001_2024-04-05T10:00:00Z/manifest.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


@dataclass
class LedgerEntry:
    """A single entry in history.tsv."""

    sequence: int
    entry_type: Literal["ingest", "rules", "balance"]
    enabled: bool
    timestamp: str
    record: dict[str, Any]

    def to_tsv_line(self) -> str:
        """Convert to TSV line for history.tsv."""
        enabled_int = 1 if self.enabled else 0
        record_json = json.dumps(self.record, ensure_ascii=False, separators=(",", ":"))
        return f"{self.sequence:04d}\t{self.entry_type}\t{enabled_int}\t{self.timestamp}\t{record_json}"

    @classmethod
    def from_tsv_line(cls, line: str) -> LedgerEntry:
        """Parse from TSV line."""
        parts = line.rstrip("\n").split("\t", 4)
        if len(parts) != 5:
            raise ValueError(f"Invalid ledger line (expected 5 columns): {line}")

        seq_str, entry_type, enabled_str, timestamp, record_json = parts

        return cls(
            sequence=int(seq_str),
            entry_type=entry_type,  # type: ignore
            enabled=enabled_str == "1",
            timestamp=timestamp,
            record=json.loads(record_json),
        )

    def get_directory(self, vault_path: Path) -> Path:
        """Get storage directory for this entry."""
        if self.entry_type == "ingest":
            return vault_path / "transactions" / f"{self.sequence:04d}_{self.timestamp}"
        elif self.entry_type == "rules":
            return vault_path / "rules"
        elif self.entry_type == "balance":
            return vault_path / "balance"
        else:
            raise ValueError(f"Unknown entry type: {self.entry_type}")

    def get_file_path(self, vault_path: Path) -> Path:
        """Get primary file path for this entry."""
        if self.entry_type == "ingest":
            # For ingest, return directory (contains multiple files)
            return self.get_directory(vault_path)
        elif self.entry_type == "rules":
            return vault_path / "rules" / f"{self.sequence:04d}_{self.timestamp}_rules.py"
        elif self.entry_type == "balance":
            return vault_path / "balance" / f"{self.sequence:04d}_{self.timestamp}_balance.tsv"
        else:
            raise ValueError(f"Unknown entry type: {self.entry_type}")


class Ledger:
    """Manager for history.tsv ledger."""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.ledger_path = vault_path / "history.tsv"

    def read_entries(self) -> list[LedgerEntry]:
        """Read all entries from history.tsv."""
        if not self.ledger_path.exists():
            return []

        entries: list[LedgerEntry] = []
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            header = f.readline()
            if not header.startswith("seq\t"):
                raise ValueError(f"Invalid ledger header: {header}")

            for line_num, line in enumerate(f, start=2):
                if not line.strip():
                    continue
                try:
                    entry = LedgerEntry.from_tsv_line(line)
                    entries.append(entry)
                except Exception as e:
                    raise ValueError(f"Failed to parse line {line_num}: {e}") from e

        return entries

    def append_entry(self, entry: LedgerEntry) -> None:
        """Append entry to history.tsv."""
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

        # Create header if file doesn't exist
        if not self.ledger_path.exists():
            with open(self.ledger_path, "w", encoding="utf-8") as f:
                f.write("seq\ttype\tenabled\ttimestamp\trecord\n")

        # Append entry
        with open(self.ledger_path, "a", encoding="utf-8") as f:
            f.write(entry.to_tsv_line() + "\n")

    def next_sequence(self) -> int:
        """Get next available sequence number."""
        entries = self.read_entries()
        if not entries:
            return 1
        return max(e.sequence for e in entries) + 1

    def get_entry(self, sequence: int) -> LedgerEntry | None:
        """Get entry by sequence number."""
        for entry in self.read_entries():
            if entry.sequence == sequence:
                return entry
        return None

    def update_enabled(self, sequence: int, enabled: bool) -> None:
        """Update the enabled flag for an entry."""
        entries = self.read_entries()

        for entry in entries:
            if entry.sequence == sequence:
                entry.enabled = enabled
                break
        else:
            raise ValueError(f"Entry {sequence} not found")

        # Rewrite entire file
        self._write_entries(entries)

    def _write_entries(self, entries: list[LedgerEntry]) -> None:
        """Rewrite history.tsv with given entries atomically."""
        import tempfile

        # Write to temp file first
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.ledger_path.parent, prefix=".history.tsv.tmp.", text=True
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as f:
                f.write("seq\ttype\tenabled\ttimestamp\trecord\n")
                for entry in entries:
                    f.write(entry.to_tsv_line() + "\n")

            # Atomic move
            Path(tmp_path).replace(self.ledger_path)
        except Exception:
            # Clean up temp file on error
            Path(tmp_path).unlink(missing_ok=True)
            raise
