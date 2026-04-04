"""Shared utilities for CSV parsing."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path


def read_file_with_encoding(path: Path) -> str:
    """Read a file with UTF-8, falling back to CP1252 then ISO-8859-1."""
    raw = path.read_bytes()

    for encoding in ["utf-8", "cp1252", "iso-8859-1"]:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Could not decode file: {path}")


def parse_german_date(s: str) -> date:
    """Parse DD.MM.YYYY or DD.MM.YY to date."""
    s = s.strip()
    for fmt in ["%d.%m.%Y", "%d.%m.%y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {s}")


def parse_german_amount(s: str) -> int:
    """Parse German number format to cents.

    '1.234,56' -> 123456
    '-1.234,56' -> -123456
    """
    s = s.strip().replace(".", "").replace(",", ".")
    return int(round(float(s) * 100))
