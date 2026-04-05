"""Vault operations for rules updates."""

from __future__ import annotations

from penny.vault.config import VaultConfig
from penny.vault.rules_store import save_rules_snapshot


def update_rules(content: str, config: VaultConfig | None = None) -> str:
    """Update rules file and create vault ledger entry.

    Args:
        content: Rules file content
        config: Optional vault config

    Returns:
        Path to saved rules file
    """
    cfg = config or VaultConfig()

    # Save the rules snapshot (this also writes to the ledger)
    rules_path = save_rules_snapshot(content, cfg)

    return str(rules_path)


def update_rules_and_apply(content: str, config: VaultConfig | None = None) -> str:
    """Append a new rules snapshot to the vault and apply it synchronously.

    This is the preferred write contract for rules changes:
    1. record the mutation in the vault
    2. apply the new rules to the projection
    3. return only after the projection reflects the active rules snapshot
    """
    from penny.runtime_rules import run_stored_rules

    cfg = config or VaultConfig()
    rules_path = update_rules(content, cfg)
    run_stored_rules(config=cfg, ensure_rules=False, include_hidden=True)
    return rules_path
