"""Pure helpers for anchor-based balance projection using vectorized operations.

The balance at a date is treated as the end-of-day balance after that day's
transactions have been applied.

Core insight: balance projection is cumulative sum with known reference points.
    balance[d] = anchor_value + (cumsum[d] - cumsum[anchor_idx])
This works for both forward and backward projection.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np


def find_effective_anchors(anchors: Iterable[dict]) -> list[dict]:
    """Deduplicate by day (keep last inserted), sort by date."""
    by_date = {}
    for anchor in anchors:
        by_date[anchor["date"]] = anchor
    return [by_date[d] for d in sorted(by_date)]


# Keep old name for compatibility
normalize_anchors = find_effective_anchors


def reanchor_range(
    cumsum: np.ndarray,
    start_idx: int,
    end_idx: int,
    anchor_idx: int,
    anchor_value: int,
) -> np.ndarray:
    """
    Return cumsum[start_idx:end_idx] shifted so value at anchor_idx equals anchor_value.

    The cumsum captures relative changes. This shifts the curve vertically
    to pass through the known anchor point.
    """
    offset = anchor_value - cumsum[anchor_idx]
    return cumsum[start_idx:end_idx] + offset


def project_backward_with_inconsistencies(
    date_strs: list[str],
    saldo_by_date: dict[str, int],
    anchors: list[dict],
) -> tuple[dict[str, int], list[dict]]:
    """Project anchors backward and record deltas at anchor boundaries.

    Algorithm:
    1. Build date index including all dates and anchor dates
    2. Compute cumsum of saldo (captures relative changes)
    3. For each anchor (latest to earliest):
       - Check inconsistency with later anchor's projection
       - Fill balance for range [prev_anchor+1, this_anchor] using reanchor
    """
    if not anchors or not date_strs:
        return {}, []

    # Build full date range including anchor dates
    anchor_dates = {a["date"] for a in anchors}
    all_dates = sorted(set(date_strs) | anchor_dates)

    # Build aligned arrays
    n = len(all_dates)
    date_to_idx = {d: i for i, d in enumerate(all_dates)}

    saldo = np.array([saldo_by_date.get(d, 0) for d in all_dates], dtype=np.int64)
    cumsum = np.cumsum(saldo)
    balance = np.full(n, np.nan)

    # Process anchors from latest to earliest
    deltas = []
    for i in range(len(anchors) - 1, -1, -1):
        anchor = anchors[i]
        anchor_idx = date_to_idx[anchor["date"]]
        anchor_value = anchor["balance_cents"]

        # Check inconsistency: what would later anchor project to this position?
        if i < len(anchors) - 1:
            later_anchor = anchors[i + 1]
            later_idx = date_to_idx[later_anchor["date"]]
            later_value = later_anchor["balance_cents"]
            # Project from later anchor to this anchor's position
            projected = cumsum[anchor_idx] + (later_value - cumsum[later_idx])
            delta = anchor_value - projected
            if abs(delta) > 1:
                deltas.append(
                    {
                        "date": anchor["date"],
                        "projected_balance": int(projected),
                        "anchor_balance": anchor_value,
                        "delta_cents": int(delta),
                    }
                )

        # Determine range this anchor owns: (prev_anchor, this_anchor]
        if i > 0:
            prev_anchor_idx = date_to_idx[anchors[i - 1]["date"]]
            start_idx = prev_anchor_idx + 1
        else:
            start_idx = 0

        end_idx = anchor_idx + 1

        # Fill balance for this range
        if start_idx < end_idx:
            balance[start_idx:end_idx] = reanchor_range(
                cumsum, start_idx, end_idx, anchor_idx, anchor_value
            )

    # Filter to requested dates and convert to dict
    result = {}
    for d in date_strs:
        idx = date_to_idx[d]
        if not np.isnan(balance[idx]):
            result[d] = int(balance[idx])

    deltas.sort(key=lambda x: x["date"])
    return result, deltas


def project_forward_from_latest_anchor(
    date_strs: list[str],
    saldo_by_date: dict[str, int],
    anchor: dict,
) -> dict[str, int]:
    """Project balances forward from the newest anchor only.

    Algorithm:
    1. Build date index including anchor date
    2. Compute cumsum of saldo
    3. Reanchor from anchor position to end of range
    """
    if not anchor or not date_strs:
        return {}

    anchor_date = anchor["date"]
    anchor_value = anchor["balance_cents"]

    # Build full date range including anchor date
    all_dates = sorted(set(date_strs) | {anchor_date})

    # Build aligned arrays
    n = len(all_dates)
    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    anchor_idx = date_to_idx[anchor_date]

    saldo = np.array([saldo_by_date.get(d, 0) for d in all_dates], dtype=np.int64)
    cumsum = np.cumsum(saldo)

    # Forward projection: from anchor to end
    balance = reanchor_range(cumsum, anchor_idx, n, anchor_idx, anchor_value)

    # Filter to requested dates from anchor onward
    result = {}
    for d in date_strs:
        if d >= anchor_date:
            idx = date_to_idx[d]
            result[d] = int(balance[idx - anchor_idx])

    return result


def build_balance_series(
    date_strs: list[str],
    saldo_by_date: dict[str, int],
    anchors: Iterable[dict],
) -> tuple[dict[str, int], list[dict], list[dict]]:
    """Build a balance series and inconsistency list from date-keyed inputs.

    Returns:
        (balances_dict, inconsistencies_list, normalized_anchors)

    The balance series uses backward projection for dates <= latest anchor,
    and forward projection for dates > latest anchor.
    """
    normalized_anchors = find_effective_anchors(anchors)
    if not normalized_anchors:
        return {}, [], []

    backward_balances, deltas = project_backward_with_inconsistencies(
        date_strs,
        saldo_by_date,
        normalized_anchors,
    )

    latest_anchor = normalized_anchors[-1]
    forward_balances = project_forward_from_latest_anchor(
        date_strs,
        saldo_by_date,
        latest_anchor,
    )

    # Combine: backward for dates <= latest anchor, forward for dates after
    latest_anchor_date = latest_anchor["date"]
    balances = {}
    for date_str in date_strs:
        if date_str <= latest_anchor_date:
            if date_str in backward_balances:
                balances[date_str] = backward_balances[date_str]
        elif date_str in forward_balances:
            balances[date_str] = forward_balances[date_str]

    return balances, deltas, normalized_anchors
