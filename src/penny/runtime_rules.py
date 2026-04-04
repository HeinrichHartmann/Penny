"""Helpers for running the persisted rules snapshot against stored transactions."""

from __future__ import annotations

from penny.classify.engine import (
    ClassificationPassResult,
    load_rules_config,
    run_classification_pass,
)
from penny.transactions import list_transactions


def run_stored_rules(
    *,
    config=None,
    ensure_rules: bool = False,
    include_hidden: bool = True,
) -> ClassificationPassResult | None:
    """Run the latest persisted rules snapshot against stored transactions."""
    from penny.vault.config import VaultConfig
    from penny.vault.rules_store import ensure_rules_snapshot, latest_rules_path
    from penny.vault.writes import apply_classifications

    cfg = config or VaultConfig()
    rules_path = ensure_rules_snapshot(cfg) if ensure_rules else latest_rules_path(cfg)
    if rules_path is None or not rules_path.exists():
        return None

    transactions = list_transactions(limit=None, neutralize=False, include_hidden=include_hidden)
    if not transactions:
        return None

    result = run_classification_pass(transactions, load_rules_config(rules_path))
    apply_classifications(result.decisions, config=cfg)
    return result
