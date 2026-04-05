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
