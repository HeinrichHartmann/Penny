"""Vault - portable event-log storage."""

from penny.vault.config import VaultConfig
from penny.vault.log import LogManager, LogEntry
from penny.vault.mutations import MutationLog, MutationRow
from penny.vault.manifests import (
    InitManifest,
    AccountCreatedManifest,
    AccountUpdatedManifest,
    AccountHiddenManifest,
    BalanceSnapshotManifest,
    IngestManifest,
    RulesManifest,
)
from penny.vault.apply import apply_ingest, apply_entry, IngestResult
from penny.vault.ingest import ingest_csv, ingest_csv_files, IngestRequest
from penny.vault.replay import ReplayEngine, ReplayResult, replay_vault
from penny.vault.startup import StartupResult, bootstrap_application_state, ensure_vault_initialized
from penny.vault.rules_store import (
    default_rules_template,
    ensure_rules_snapshot,
    latest_rules_path,
    save_rules_snapshot,
)

__all__ = [
    # Config
    "VaultConfig",
    # Log
    "LogManager",
    "LogEntry",
    "MutationLog",
    "MutationRow",
    # Manifests
    "InitManifest",
    "AccountCreatedManifest",
    "AccountUpdatedManifest",
    "AccountHiddenManifest",
    "BalanceSnapshotManifest",
    "IngestManifest",
    "RulesManifest",
    # Apply
    "apply_ingest",
    "apply_entry",
    "IngestResult",
    # Ingest service
    "ingest_csv",
    "ingest_csv_files",
    "IngestRequest",
    # Replay
    "ReplayEngine",
    "ReplayResult",
    "replay_vault",
    # Startup
    "StartupResult",
    "bootstrap_application_state",
    "ensure_vault_initialized",
    # Rules storage
    "default_rules_template",
    "ensure_rules_snapshot",
    "latest_rules_path",
    "save_rules_snapshot",
]
