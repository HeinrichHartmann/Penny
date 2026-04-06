"""Base interfaces for bank detection and format parsing."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import BinaryIO

    from penny.transactions import Transaction


_VAULT_PREFIX_PATTERN = re.compile(r"^PI\d+_(.+)$")


def normalize_csv_filename(filename: str) -> str:
    """Strip Penny's vault storage prefix from a filename when present."""
    match = _VAULT_PREFIX_PATTERN.match(filename)
    return match.group(1) if match else filename


@dataclass(frozen=True)
class CsvSource:
    """Logical CSV input with a stable filename and reopenable byte source."""

    filename: str
    open_file: Callable[[], BinaryIO]

    def __post_init__(self) -> None:
        object.__setattr__(self, "filename", normalize_csv_filename(self.filename))

    @classmethod
    def from_content(cls, filename: str, content: str | bytes) -> CsvSource:
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        return cls(filename=filename, open_file=lambda: BytesIO(raw_bytes))

    @classmethod
    def from_path(cls, path: Path, *, filename: str | None = None) -> CsvSource:
        return cls(filename=filename or path.name, open_file=lambda: path.open("rb"))

    @cached_property
    def raw_bytes(self) -> bytes:
        with self.open_file() as handle:
            raw = handle.read()

        if isinstance(raw, str):
            return raw.encode("utf-8")
        return raw

    @cached_property
    def text(self) -> str:
        for encoding in ["utf-8", "cp1252", "iso-8859-1"]:
            try:
                return self.raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue

        raise ValueError(f"Could not decode file: {self.filename}")


@dataclass
class BalanceSnapshot:
    """Balance snapshot extracted from CSV.

    These are embedded in bank exports (e.g., "Neuer Kontostand" in Comdirect).
    """

    subaccount_type: str  # e.g., "giro", "visa"
    balance_cents: int
    snapshot_date: date
    note: str = ""


@dataclass
class DetectionResult:
    """Result of file detection without transaction parsing."""

    parser_name: str
    bank: str
    bank_account_number: str | None
    detected_subaccounts: list[str] = field(default_factory=list)
    iban: str | None = None
    confidence: float = 1.0


class BankModule(ABC):
    """Bank-specific detection and format binding.

    Each bank has:
    - Inference logic (filename patterns, content signatures)
    - A format parser (may be shared across banks)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable bank name."""

    @property
    @abstractmethod
    def bank(self) -> str:
        """Bank identifier (lowercase)."""

    @property
    @abstractmethod
    def filename_pattern(self) -> re.Pattern[str]:
        """Regex for matching filenames."""

    @abstractmethod
    def match(self, source: CsvSource) -> bool:
        """Return True if this bank can handle the file."""

    @abstractmethod
    def detect(self, source: CsvSource) -> DetectionResult:
        """Detect account metadata without parsing transactions."""

    @abstractmethod
    def parse(self, source: CsvSource, account_id: int) -> list[Transaction]:
        """Parse transactions."""

    def extract_balances(self, source: CsvSource) -> list[BalanceSnapshot]:
        """Extract balance snapshots from CSV.

        Override in subclasses that have embedded balance info.
        Returns empty list by default.
        """
        return []
