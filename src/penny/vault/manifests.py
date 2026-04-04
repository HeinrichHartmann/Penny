"""Manifest schemas for vault log entries."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class BaseManifest:
    """Base class for all manifests."""

    schema_version: int = 1
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def write(self, path: Path) -> None:
        """Write manifest to file."""
        path.write_text(self.to_json())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseManifest:
        """Create manifest from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> BaseManifest:
        """Create manifest from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def read(cls, path: Path) -> BaseManifest:
        """Read manifest from file."""
        return cls.from_json(path.read_text())


@dataclass
class InitManifest(BaseManifest):
    """Vault initialization entry."""

    type: Literal["init"] = "init"
    app_version: str = ""


@dataclass
class AccountCreatedManifest(BaseManifest):
    """Account creation entry."""

    type: Literal["account_created"] = "account_created"
    bank: str = ""
    bank_account_number: str | None = None
    display_name: str | None = None
    iban: str | None = None


@dataclass
class AccountUpdatedManifest(BaseManifest):
    """Account metadata update entry."""

    type: Literal["account_updated"] = "account_updated"
    account_id: int = 0
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountHiddenManifest(BaseManifest):
    """Account hidden (soft-delete) entry."""

    type: Literal["account_hidden"] = "account_hidden"
    account_id: int = 0


@dataclass
class BalanceSnapshotManifest(BaseManifest):
    """Balance snapshot entry."""

    type: Literal["balance_snapshot"] = "balance_snapshot"
    account_id: int = 0
    subaccount_type: str = ""
    snapshot_date: str = ""
    balance_cents: int = 0
    note: str | None = None


@dataclass
class IngestManifest(BaseManifest):
    """CSV ingest entry."""

    type: Literal["ingest"] = "ingest"
    csv_files: list[str] = field(default_factory=list)
    parser: str = ""
    parser_version: str = ""
    app_version: str = ""
    status: Literal["applied", "failed"] = "applied"


@dataclass
class RulesManifest(BaseManifest):
    """Rules update entry."""

    type: Literal["rules"] = "rules"
    app_version: str = ""


# Type alias for all manifest types
ManifestType = (
    InitManifest
    | AccountCreatedManifest
    | AccountUpdatedManifest
    | AccountHiddenManifest
    | BalanceSnapshotManifest
    | IngestManifest
    | RulesManifest
)

# Mapping from type string to manifest class
MANIFEST_TYPES: dict[str, type[BaseManifest]] = {
    "init": InitManifest,
    "account_created": AccountCreatedManifest,
    "account_updated": AccountUpdatedManifest,
    "account_hidden": AccountHiddenManifest,
    "balance_snapshot": BalanceSnapshotManifest,
    "ingest": IngestManifest,
    "rules": RulesManifest,
}


def load_manifest(path: Path) -> ManifestType:
    """Load a manifest file and return the appropriate typed manifest."""
    data = json.loads(path.read_text())
    manifest_type = data.get("type")

    if manifest_type not in MANIFEST_TYPES:
        raise ValueError(f"Unknown manifest type: {manifest_type}")

    cls = MANIFEST_TYPES[manifest_type]
    return cls.from_dict(data)
