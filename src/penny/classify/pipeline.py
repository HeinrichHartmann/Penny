"""Classification and transfer linking pipeline.

Shared logic for both CLI and API to run classification + transfer linking.
"""

from dataclasses import dataclass
from types import ModuleType

from penny.classify.engine import LoadedRulesConfig, run_classification_pass
from penny.transactions import Transaction, apply_classifications, apply_groups
from penny.transfers import link_transfers


@dataclass
class PipelineResult:
    """Result of the full classification + linking pipeline."""

    # Classification stats
    matched_count: int
    default_count: int
    category_counts: dict[str, int]

    # Transfer linking stats (None if no predicate defined)
    transfer_groups: int | None = None
    transfer_linked: int | None = None
    transfer_standalone: int | None = None


def run_full_classification(
    transactions: list[Transaction],
    config: LoadedRulesConfig,
    *,
    persist: bool = True,
) -> PipelineResult:
    """Run classification and transfer linking on transactions.

    Args:
        transactions: List of transactions to classify
        config: Loaded rules configuration
        persist: If True, persist changes to database

    Returns:
        PipelineResult with classification and linking statistics
    """
    # Run classification
    result = run_classification_pass(transactions, config)

    if persist:
        apply_classifications(result.decisions)

    # Update transaction categories in memory for transfer linking
    decisions_by_fp = {d.fingerprint: d for d in result.decisions}
    for tx in transactions:
        decision = decisions_by_fp.get(tx.fingerprint)
        if decision:
            tx.category = decision.category

    # Extract transfer settings from rules module
    module: ModuleType | None = getattr(config, "module", None)
    transfer_prefix = getattr(module, "TRANSFER_PREFIX", "transfer/") if module else "transfer/"
    transfer_window = getattr(module, "TRANSFER_WINDOW_DAYS", 10) if module else 10
    transfer_predicate = getattr(module, "in_same_transfer_group", None) if module else None

    transfer_groups = None
    transfer_linked = None
    transfer_standalone = None

    if transfer_predicate:
        transfer_result = link_transfers(
            transactions,
            transfer_predicate,
            prefix=transfer_prefix,
            window_days=transfer_window,
        )

        if persist:
            apply_groups(transfer_result.assignments)

        transfer_groups = transfer_result.groups_found
        transfer_linked = transfer_result.grouped_entries
        transfer_standalone = transfer_result.standalone_entries

    return PipelineResult(
        matched_count=result.matched_count,
        default_count=result.default_count,
        category_counts=result.category_counts,
        transfer_groups=transfer_groups,
        transfer_linked=transfer_linked,
        transfer_standalone=transfer_standalone,
    )
