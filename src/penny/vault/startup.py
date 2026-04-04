"""Application startup helpers for vault-backed state."""

from __future__ import annotations

from dataclasses import dataclass

from penny import __version__
from penny.vault.config import VaultConfig
from penny.vault.log import LogManager
from penny.vault.manifests import InitManifest
from penny.vault.replay import ReplayResult, replay_vault


@dataclass(frozen=True)
class StartupResult:
    """Outcome of preparing app state from the vault."""

    init_entry_created: bool
    replay_result: ReplayResult


def ensure_vault_initialized(config: VaultConfig | None = None) -> bool:
    """Ensure the vault exists and has an initial log entry.

    Returns True if an init entry was created during this call.
    """
    if config is None:
        config = VaultConfig()

    log = LogManager(config)
    if log.count() > 0:
        return False

    log.append(
        "init",
        InitManifest(app_version=__version__),
    )
    return True


def bootstrap_application_state(config: VaultConfig | None = None) -> StartupResult:
    """Initialize the vault if needed and replay it into the SQLite projection."""
    if config is None:
        config = VaultConfig()

    init_entry_created = ensure_vault_initialized(config)
    replay_result = replay_vault(config)
    return StartupResult(
        init_entry_created=init_entry_created,
        replay_result=replay_result,
    )
