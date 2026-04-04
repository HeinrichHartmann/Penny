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
    demo_data_loaded: bool
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

    On first initialization, loads demo data to provide a populated UI experience.
    Replay also restores runtime classifications from the latest rules snapshot.
    """
    from penny.demo_bootstrap import bootstrap_demo_data

    if config is None:
        config = VaultConfig()

    init_entry_created = ensure_vault_initialized(config)

    # Load demo data on first initialization
    demo_data_loaded = bootstrap_demo_data(config)

    ensure_rules_snapshot(config)
    replay_result = replay_vault(config)

    return StartupResult(
        init_entry_created=init_entry_created,
        demo_data_loaded=demo_data_loaded,
        replay_result=replay_result,
    )
