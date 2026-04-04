"""Base interfaces for bank detection and format parsing."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from penny.transactions.models import Transaction


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
    def match(self, filename: str, content: str) -> bool:
        """Return True if this bank can handle the file."""

    @abstractmethod
    def detect(self, filename: str, content: str) -> DetectionResult:
        """Detect account metadata without parsing transactions."""

    @abstractmethod
    def parse(self, filename: str, content: str, account_id: int) -> list[Transaction]:
        """Parse transactions."""
