"""File encoding and parser matching helpers."""

from __future__ import annotations

from pathlib import Path

from penny.import_.base import ParserModule
from penny.import_.parsers import ComdirectParser


class DetectionError(ValueError):
    """Raised when a file cannot be detected cleanly."""


def read_file_with_encoding(path: Path) -> str:
    """Read a file with UTF-8 and CP1252 fallback."""

    raw = path.read_bytes()

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def get_parsers() -> list[ParserModule]:
    """Return all built-in parsers."""

    return [ComdirectParser()]


def get_supported_csv_types() -> list[str]:
    """Return the supported parser identifiers."""

    return [parser.bank for parser in get_parsers()]


def get_parser_by_type(csv_type: str) -> ParserModule:
    """Return a parser by its identifier."""

    normalized = csv_type.lower()
    for parser in get_parsers():
        if parser.bank == normalized:
            return parser

    supported = ", ".join(get_supported_csv_types())
    raise DetectionError(f"Unsupported csv type: {csv_type}. Supported types: {supported}")


def _validate_parser_match(parser: ParserModule, filename: str, content: str) -> ParserModule:
    if parser.match(filename, content):
        return parser

    content_signature_matches = getattr(parser, "content_signature_matches", None)
    if callable(content_signature_matches) and content_signature_matches(content):
        if not parser.filename_pattern.match(filename):
            expected = getattr(parser, "expected_filename_hint", parser.filename_pattern.pattern)
            raise DetectionError(
                "Filename does not match expected export format. "
                f"Expected: {expected}"
            )

    raise DetectionError(f"File does not match selected parser: {parser.bank}")


def match_file(filename: str, content: str, csv_type: str | None = None) -> ParserModule:
    """Return the parser for a file or raise a detection error."""

    if csv_type:
        return _validate_parser_match(get_parser_by_type(csv_type), filename, content)

    parsers = get_parsers()
    for parser in parsers:
        if parser.match(filename, content):
            return parser

    for parser in parsers:
        content_signature_matches = getattr(parser, "content_signature_matches", None)
        if callable(content_signature_matches) and content_signature_matches(content):
            if not parser.filename_pattern.match(filename):
                expected = getattr(parser, "expected_filename_hint", parser.filename_pattern.pattern)
                raise DetectionError(
                    "Filename does not match expected export format. "
                    f"Expected: {expected}"
                )

    raise DetectionError(f"Unknown file format: {filename}")
