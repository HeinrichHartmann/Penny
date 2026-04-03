"""Comdirect CSV parser."""

from __future__ import annotations

import csv
import re

from penny.import_.base import DetectionResult, ParserModule
from penny.import_.parsers.buchungstext import extract_memo, extract_payee, extract_reference
from penny.import_.utils import parse_german_amount, parse_german_date
from penny.transactions import Transaction, generate_fingerprint


class ComdirectParser(ParserModule):
    """Parse vanilla Comdirect CSV exports."""

    name = "Comdirect"
    bank = "comdirect"
    filename_pattern = re.compile(r"^umsaetze_(\d+)_[\d-]+(?:\(\d+\))?\.csv$")
    expected_filename_hint = (
        "umsaetze_<account-number>_YYYYMMDD-HHMM.csv "
        "(or umsaetze_<account-number>_YYYYMMDD-HHMM(1).csv)"
    )

    SECTION_PATTERNS = {
        "giro": ["Umsätze Girokonto", "Umsätze Verrechnungskonto"],
        "visa": ["Umsätze Visa-Karte"],
        "tagesgeld": ["Umsätze Tagesgeld", "Umsätze Tagesgeld PLUS-Konto"],
        "depot": ["Umsätze Depot"],
    }

    def content_signature_matches(self, content: str) -> bool:
        """Return True when the file content looks like Comdirect."""

        return any(
            marker in content
            for markers in self.SECTION_PATTERNS.values()
            for marker in markers
        )

    def match(self, filename: str, content: str) -> bool:
        return bool(self.filename_pattern.match(filename)) and self.content_signature_matches(content)

    def detect(self, filename: str, content: str) -> DetectionResult:
        match = self.filename_pattern.match(filename)
        if match is None:
            raise ValueError(
                "Filename does not match expected Comdirect format: "
                f"{self.expected_filename_hint}"
            )

        subaccounts = [
            subtype
            for subtype, patterns in self.SECTION_PATTERNS.items()
            if any(pattern in content for pattern in patterns)
        ]

        return DetectionResult(
            parser_name=self.name,
            bank=self.bank,
            bank_account_number=match.group(1),
            detected_subaccounts=subaccounts,
            confidence=1.0,
        )

    def parse(self, filename: str, content: str, account_id: int) -> list[Transaction]:
        """Parse Comdirect transactions."""

        if not self.filename_pattern.match(filename):
            raise ValueError(
                "Filename does not match expected Comdirect format: "
                f"{self.expected_filename_hint}"
            )

        transactions: list[Transaction] = []
        for section_header, section_content in self._split_sections(content):
            subaccount = self._detect_subaccount(section_header)
            rows = self._read_section_rows(section_content)
            header_index, headers = self._find_header_row(rows)
            for raw_row in rows[header_index + 1 :]:
                row = self._row_to_dict(headers, raw_row)
                transaction = self._parse_row(row, account_id=account_id, subaccount=subaccount)
                if transaction is not None:
                    transactions.append(transaction)
        return transactions

    def _split_sections(self, content: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_header: str | None = None
        current_lines: list[str] = []

        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('"Umsätze '):
                if current_header is not None:
                    sections.append((current_header, "\n".join(current_lines)))
                current_header = next(csv.reader([line], delimiter=";"))[0].strip()
                current_lines = []
                continue

            if current_header is not None:
                current_lines.append(line)

        if current_header is not None:
            sections.append((current_header, "\n".join(current_lines)))

        return sections

    def _detect_subaccount(self, section_header: str) -> str:
        header_lower = section_header.lower()
        if "visa" in header_lower:
            return "visa"
        if "tagesgeld" in header_lower:
            return "tagesgeld"
        if "depot" in header_lower:
            return "depot"
        return "giro"

    def _read_section_rows(self, section_content: str) -> list[list[str]]:
        return [
            [cell.strip() for cell in row]
            for row in csv.reader(section_content.splitlines(), delimiter=";")
            if row
        ]

    def _find_header_row(self, rows: list[list[str]]) -> tuple[int, list[str]]:
        for index, row in enumerate(rows):
            if "Buchungstag" in row and "Umsatz in EUR" in row:
                return index, row
        raise ValueError("Could not find Comdirect header row")

    def _row_to_dict(self, headers: list[str], row: list[str]) -> dict[str, str]:
        values = row + [""] * max(0, len(headers) - len(row))
        return {header: values[index].strip() for index, header in enumerate(headers)}

    def _parse_row(self, row: dict[str, str], *, account_id: int, subaccount: str) -> Transaction | None:
        booking_date = row.get("Buchungstag", "").strip()
        amount_value = row.get("Umsatz in EUR", "").strip()
        if not booking_date or booking_date in {"Alter Kontostand", "Neuer Kontostand"}:
            return None
        if booking_date == "offen" or not amount_value:
            return None

        posting_text = row.get("Buchungstext", "").strip()
        transaction_type = row.get("Vorgang", "").strip()
        value_date_raw = (
            row.get("Wertstellung (Valuta)", "").strip()
            or row.get("Wertstellung", "").strip()
            or row.get("Umsatztag", "").strip()
        )

        date_value = parse_german_date(booking_date)
        value_date = None if not value_date_raw or value_date_raw == "--" else parse_german_date(value_date_raw)
        amount_cents = parse_german_amount(amount_value)

        if subaccount == "visa":
            payee = posting_text or transaction_type
            memo = posting_text or transaction_type
            reference = row.get("Referenz", "").strip() or extract_reference(posting_text)
        else:
            payee = extract_payee(posting_text) or transaction_type
            memo = extract_memo(posting_text) or transaction_type
            reference = extract_reference(posting_text)

        fingerprint = generate_fingerprint(account_id, date_value, amount_cents, payee, reference)

        return Transaction(
            fingerprint=fingerprint,
            account_id=account_id,
            subaccount_type=subaccount,
            date=date_value,
            payee=payee,
            memo=memo,
            amount_cents=amount_cents,
            value_date=value_date,
            transaction_type=transaction_type,
            reference=reference,
            raw_buchungstext=posting_text,
            raw_row=row,
        )
