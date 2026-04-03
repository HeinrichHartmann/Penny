"""Base parser interfaces for CSV import."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from penny.transactions.models import Transaction


@dataclass
class DetectionResult:
    """Result of file detection without transaction parsing."""

    parser_name: str
    bank: str
    bank_account_number: str | None
    detected_subaccounts: list[str]
    confidence: float


class ParserModule(ABC):
    """Base class for CSV parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable parser name."""

    @property
    @abstractmethod
    def bank(self) -> str:
        """Bank identifier."""

    @property
    @abstractmethod
    def filename_pattern(self) -> re.Pattern[str]:
        """Regex for matching filenames."""

    @abstractmethod
    def match(self, filename: str, content: str) -> bool:
        """Return True if this parser can handle the file."""

    @abstractmethod
    def detect(self, filename: str, content: str) -> DetectionResult:
        """Detect metadata without parsing transactions."""

    @abstractmethod
    def parse(self, filename: str, content: str, account_id: int) -> list[Transaction]:
        """Parse transactions for the selected account."""
