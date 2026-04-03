"""CSV import utility helpers."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def parse_german_date(value: str):
    """Parse a DD.MM.YYYY date."""

    return datetime.strptime(value.strip(), "%d.%m.%Y").date()


def parse_german_amount(value: str) -> int:
    """Parse a German amount string into cents."""

    normalized = value.strip().replace(".", "").replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid German amount: {value}") from exc
    return int((amount * 100).quantize(Decimal("1")))
