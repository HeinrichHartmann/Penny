"""Sparkasse bank module."""

from __future__ import annotations

import re

from penny.ingest.base import BankModule, DetectionResult
from penny.ingest.formats.camt_v8 import CamtV8Parser
from penny.transactions import Transaction


class SparkasseBank(BankModule):
    """Sparkasse bank - uses CAMT V8 CSV format."""

    name = "Sparkasse"
    bank = "sparkasse"
    filename_pattern = re.compile(r"^\d{8}-\d+-umsatz-camt52v8(?:\(\d+\))?\.CSV$", re.IGNORECASE)
    expected_filename_hint = "YYYYMMDD-ACCOUNTNUMBER-umsatz-camt52v8.CSV (or ...camt52v8(1).CSV)"

    def __init__(self) -> None:
        self._parser = CamtV8Parser()

    def content_signature_matches(self, content: str) -> bool:
        """Return True when the file content looks like CAMT V8."""
        return '"Auftragskonto"' in content and '"Buchungstag"' in content

    def match(self, filename: str, content: str) -> bool:
        if not self.filename_pattern.match(filename):
            return False
        return self.content_signature_matches(content)

    def detect(self, filename: str, content: str) -> DetectionResult:
        match = self.filename_pattern.match(filename)
        if match is None:
            raise ValueError(
                f"Filename does not match expected Sparkasse format: {self.expected_filename_hint}"
            )

        # Extract account number from filename: YYYYMMDD-ACCOUNTNUM-umsatz-camt52v8.CSV
        parts = filename.split("-")
        account_number = parts[1] if len(parts) >= 2 else None

        # Extract IBAN from content
        iban = self._parser.extract_iban(content)

        return DetectionResult(
            parser_name=self.name,
            bank=self.bank,
            bank_account_number=account_number,
            iban=iban,
            detected_subaccounts=["giro"],
            confidence=1.0,
        )

    def parse(self, filename: str, content: str, account_id: int) -> list[Transaction]:
        """Parse Sparkasse CAMT V8 transactions."""
        return self._parser.parse(content, account_id)
