"""Vault operations for rules updates."""

from __future__ import annotations

from penny.vault import LogManager, VaultConfig
from penny.vault.manifests import RulesManifest
from penny.vault.rules_store import save_rules_snapshot


def update_rules(content: str, config: VaultConfig | None = None) -> str:
    """Update rules file and create vault log entry.

    Args:
        content: Rules file content
        config: Optional vault config

    Returns:
        Path to saved rules file
    """
    cfg = config or VaultConfig()

    # Save the rules snapshot to rules/ directory
    rules_path = save_rules_snapshot(content, cfg)

    # Create vault log entry for the update
    manifest = RulesManifest()
    log = LogManager(cfg)
    log.append(
        entry_type="rules",
        manifest=manifest,  # type: ignore
        content_files=None,
    )

    return str(rules_path)
