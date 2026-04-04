"""Comdirect Buchungstext field extraction."""

from __future__ import annotations

import re


POSTING_TEXT_FIELDS = [
    "Buchungstext",
    "Empfänger",
    "Auftraggeber",
    "Zahlungspflichtiger",
    "Kto/IBAN",
    "BLZ/BIC",
    "Ref",
]


def extract_field(posting_text: str, field: str) -> str | None:
    """Extract a field value from structured Buchungstext."""
    parts = posting_text.split(field)
    if len(parts) < 2:
        return None

    pattern = "|".join(re.escape(marker) for marker in POSTING_TEXT_FIELDS)
    raw_content = re.split(f"({pattern})", parts[1], maxsplit=1)[0]
    value = re.sub(r"^[:.\s]+|\s+$", "", raw_content)
    return value or None


def extract_payee(text: str) -> str:
    """Extract the preferred payee field."""
    return (
        extract_field(text, "Empfänger")
        or extract_field(text, "Zahlungspflichtiger")
        or extract_field(text, "Auftraggeber")
        or ""
    )


def extract_memo(text: str) -> str:
    """Extract the memo from Buchungstext."""
    return extract_field(text, "Buchungstext") or text.strip()


def extract_reference(text: str) -> str | None:
    """Extract the Ref. value from Buchungstext."""
    return extract_field(text, "Ref")
