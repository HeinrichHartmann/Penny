"""Application startup helpers for vault-backed state."""

from __future__ import annotations

from dataclasses import dataclass

from penny.vault.config import VaultConfig
from penny.vault.replay import ReplayResult, replay_vault


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


def _run_classification() -> None:
    """Run classification rules on all transactions.

    Silently skips if no rules file exists or if classification fails.
    """
    try:
        from penny.classify import load_rules_config, run_classification_pass
        from penny.transactions import apply_classifications, list_transactions
        from penny.vault import ensure_rules_snapshot

        rules_path = ensure_rules_snapshot()
        if not rules_path or not rules_path.exists():
            return

        config = load_rules_config(rules_path)
        transactions = list_transactions(limit=None, neutralize=False)
        if not transactions:
            return

        result = run_classification_pass(transactions, config)
        apply_classifications(result.decisions)
    except Exception:
        pass  # Silently skip if classification fails


def bootstrap_application_state(config: VaultConfig | None = None) -> StartupResult:
    """Initialize the vault if needed and replay it into the SQLite projection.

    On first initialization, loads demo data to provide a populated UI experience.
    After replay, runs classification rules to categorize transactions.
    """
    from penny.demo_bootstrap import bootstrap_demo_data

    if config is None:
        config = VaultConfig()

    init_entry_created = ensure_vault_initialized(config)

    # Load demo data on first initialization
    demo_data_loaded = bootstrap_demo_data(config)

    replay_result = replay_vault(config)

    # Run classification after replay
    _run_classification()

    return StartupResult(
        init_entry_created=init_entry_created,
        demo_data_loaded=demo_data_loaded,
        replay_result=replay_result,
    )
