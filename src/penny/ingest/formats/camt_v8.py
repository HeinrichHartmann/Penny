"""CAMT52 V8 CSV format parser.

Used by: Sparkasse, potentially other German banks.

Columns:
- Auftragskonto (own IBAN)
- Buchungstag
- Valutadatum
- Buchungstext (transaction type)
- Verwendungszweck (memo)
- Glaeubiger ID
- Mandatsreferenz
- Kundenreferenz (End-to-End)
- Sammlerreferenz
- Lastschrift Ursprungsbetrag
- Auslagenersatz Ruecklastschrift
- Beguenstigter/Zahlungspflichtiger (payee)
- Kontonummer/IBAN (counterparty)
- BIC (SWIFT-Code)
- Betrag
- Waehrung
- Info
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from penny.ingest.formats.utils import parse_german_amount, parse_german_date
from penny.transactions import Transaction, generate_fingerprint

if TYPE_CHECKING:
    pass


class CamtV8Parser:
    """Parse CAMT52 V8 CSV format."""

    COLUMN_MAP = {
        "iban": "Auftragskonto",
        "date": "Buchungstag",
        "value_date": "Valutadatum",
        "transaction_type": "Buchungstext",
        "memo": "Verwendungszweck",
        "payee": "Beguenstigter/Zahlungspflichtiger",
        "counterparty_iban": "Kontonummer/IBAN",
        "counterparty_bic": "BIC (SWIFT-Code)",
        "amount": "Betrag",
        "reference": "Kundenreferenz (End-to-End)",
        "creditor_id": "Glaeubiger ID",
        "mandate_ref": "Mandatsreferenz",
        "currency": "Waehrung",
        "info": "Info",
    }

    def parse(self, content: str, account_id: int) -> list[Transaction]:
        """Parse CAMT V8 CSV content into transactions."""
        transactions: list[Transaction] = []

        lines = content.splitlines()
        reader = csv.DictReader(lines, delimiter=";")

        for row in reader:
            tx = self._parse_row(row, account_id)
            if tx is not None:
                transactions.append(tx)

        return transactions

    def _parse_row(self, row: dict[str, str], account_id: int) -> Transaction | None:
        """Parse a single CSV row."""
        date_str = row.get(self.COLUMN_MAP["date"], "").strip()
        amount_str = row.get(self.COLUMN_MAP["amount"], "").strip()

        if not date_str or not amount_str:
            return None

        # Skip zero-amount rows (like ABSCHLUSS)
        try:
            amount_cents = parse_german_amount(amount_str)
        except ValueError:
            return None

        if amount_cents == 0:
            return None

        date_value = parse_german_date(date_str)

        value_date_str = row.get(self.COLUMN_MAP["value_date"], "").strip()
        value_date = parse_german_date(value_date_str) if value_date_str else None

        payee = row.get(self.COLUMN_MAP["payee"], "").strip()
        memo = row.get(self.COLUMN_MAP["memo"], "").strip()
        transaction_type = row.get(self.COLUMN_MAP["transaction_type"], "").strip()
        reference = row.get(self.COLUMN_MAP["reference"], "").strip() or None

        # Use payee or transaction_type as fallback
        if not payee:
            payee = transaction_type or "Unknown"
        if not memo:
            memo = transaction_type or ""

        fingerprint = generate_fingerprint(account_id, date_value, amount_cents, payee, reference)

        return Transaction(
            fingerprint=fingerprint,
            account_id=account_id,
            subaccount_type="giro",  # CAMT V8 is single-account
            date=date_value,
            payee=payee,
            memo=memo,
            amount_cents=amount_cents,
            value_date=value_date,
            transaction_type=transaction_type,
            reference=reference,
            raw_buchungstext=memo,
            raw_row=dict(row),
        )

    def extract_iban(self, content: str) -> str | None:
        """Extract own IBAN from first data row."""
        lines = content.splitlines()
        reader = csv.DictReader(lines, delimiter=";")

        for row in reader:
            iban = row.get(self.COLUMN_MAP["iban"], "").strip()
            if iban:
                return iban

        return None
