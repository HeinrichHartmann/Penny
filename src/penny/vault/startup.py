"""Application startup helpers for vault-backed state."""

from __future__ import annotations

from dataclasses import dataclass

from penny.vault.config import VaultConfig
from penny.vault.replay import ReplayResult, replay_vault
from penny.vault.rules_store import ensure_rules_snapshot


@dataclass(frozen=True)
class StartupResult:
    """Outcome of preparing app state from the vault."""

    init_entry_created: bool
    replay_result: ReplayResult


def ensure_vault_initialized(config: VaultConfig | None = None) -> bool:
    """Ensure the portable storage structure exists."""
    if config is None:
        config = VaultConfig()

    if config.is_initialized():
        return False

    config.initialize()
    return True


def bootstrap_application_state(config: VaultConfig | None = None) -> StartupResult:
    """Initialize the vault if needed and replay it into the SQLite projection.

    Replay restores runtime classifications from the latest rules snapshot.
    Demo data can be imported manually via the Import view.
    """
    if config is None:
        config = VaultConfig()

    init_entry_created = ensure_vault_initialized(config)

    # Demo data is now imported manually via Import view button
    # (removed auto-bootstrap to allow users to start with empty vault)

    ensure_rules_snapshot(config)
    replay_result = replay_vault(config)

    return StartupResult(
        init_entry_created=init_entry_created,
        replay_result=replay_result,
    )
