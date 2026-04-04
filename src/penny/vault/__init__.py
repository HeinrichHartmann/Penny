"""Vault - portable event-log storage."""

from penny.vault.apply import IngestResult, apply_entry, apply_ingest
from penny.vault.config import VaultConfig
from penny.vault.ingest import IngestRequest, ingest_csv, ingest_csv_files
from penny.vault.log import LogEntry, LogManager
from penny.vault.manifests import (
    AccountCreatedManifest,
    AccountHiddenManifest,
    AccountUpdatedManifest,
    BalanceSnapshotManifest,
    IngestManifest,
    InitManifest,
    RulesManifest,
)
from penny.vault.mutations import MutationLog, MutationRow
from penny.vault.replay import ReplayEngine, ReplayResult, apply_pending_mutations, replay_vault
from penny.vault.rules_store import (
    default_rules_template,
    ensure_rules_snapshot,
    latest_rules_path,
    save_rules_snapshot,
)
from penny.vault.startup import StartupResult, bootstrap_application_state, ensure_vault_initialized
from penny.vault.writes import (
    apply_classifications,
    apply_groups,
    create_account,
    hide_account,
    store_transactions,
    update_account,
    upsert_subaccounts,
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
    "apply_pending_mutations",
    # Startup
    "StartupResult",
    "bootstrap_application_state",
    "ensure_vault_initialized",
    # Rules storage
    "default_rules_template",
    "ensure_rules_snapshot",
    "latest_rules_path",
    "save_rules_snapshot",
    # Write surface
    "create_account",
    "update_account",
    "hide_account",
    "upsert_subaccounts",
    "store_transactions",
    "apply_classifications",
    "apply_groups",
]
