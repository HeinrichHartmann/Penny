"""Pure helpers for anchor-based balance projection.

The balance at a date is treated as the end-of-day balance after that day's
transactions have been applied.
"""

from __future__ import annotations

from typing import Iterable


def normalize_anchors(anchors: Iterable[dict]) -> list[dict]:
    """Sort anchors by date and keep only the last-added anchor per day."""
    anchors_by_date = {}
    for anchor in anchors:
        anchors_by_date[anchor["date"]] = anchor
    return [anchors_by_date[date_str] for date_str in sorted(anchors_by_date)]


def project_backward_with_inconsistencies(
    date_strs: list[str],
    saldo_by_date: dict[str, int],
    anchors: list[dict],
) -> tuple[dict[str, int], list[dict]]:
    """Project anchors backward and record deltas at anchor boundaries."""
    if not anchors:
        return {}, []
    if not date_strs:
        return {}, []

    remaining_anchors = list(anchors)
    next_anchor = remaining_anchors.pop() if remaining_anchors else None
    balances: dict[str, int] = {}
    deltas: list[dict] = []
    current_balance: int | None = None

    # Handle anchors that are AFTER the date range - project backward from them
    last_date = date_strs[-1]
    while next_anchor and next_anchor["date"] > last_date:
        if current_balance is not None:
            # There's already a later anchor; check for inconsistency
            anchor_balance = next_anchor["balance_cents"]
            delta = anchor_balance - current_balance
            if abs(delta) > 1:
                deltas.append(
                    {
                        "date": next_anchor["date"],
                        "projected_balance": current_balance,
                        "anchor_balance": anchor_balance,
                        "delta_cents": delta,
                    }
                )
        current_balance = next_anchor["balance_cents"]
        next_anchor = remaining_anchors.pop() if remaining_anchors else None

    for index in range(len(date_strs) - 1, -1, -1):
        date_str = date_strs[index]

        if next_anchor and date_str == next_anchor["date"]:
            anchor_balance = next_anchor["balance_cents"]
            if current_balance is not None:
                delta = anchor_balance - current_balance
                if abs(delta) > 1:
                    deltas.append(
                        {
                            "date": date_str,
                            "projected_balance": current_balance,
                            "anchor_balance": anchor_balance,
                            "delta_cents": delta,
                        }
                    )
            current_balance = anchor_balance
            next_anchor = remaining_anchors.pop() if remaining_anchors else None

        if current_balance is None:
            continue

        balances[date_str] = current_balance
        current_balance -= saldo_by_date.get(date_str, 0)

    deltas.sort(key=lambda item: item["date"])
    return balances, deltas


def project_forward_from_latest_anchor(
    date_strs: list[str],
    saldo_by_date: dict[str, int],
    anchor: dict,
) -> dict[str, int]:
    """Project balances forward from the newest anchor only."""
    if not anchor:
        return {}

    anchor_date = anchor["date"]
    current_balance = anchor["balance_cents"]
    started = False
    balances: dict[str, int] = {}

    for index, date_str in enumerate(date_strs):
        if not started:
            if date_str < anchor_date:
                continue
            started = True
            if date_str > anchor_date:
                current_balance += saldo_by_date.get(date_str, 0)

        balances[date_str] = current_balance

        if index + 1 < len(date_strs):
            next_date = date_strs[index + 1]
            current_balance += saldo_by_date.get(next_date, 0)

    return balances


def build_balance_series(
    date_strs: list[str],
    saldo_by_date: dict[str, int],
    anchors: Iterable[dict],
) -> tuple[dict[str, int], list[dict], list[dict]]:
    """Build a balance series and inconsistency list from date-keyed inputs."""
    normalized_anchors = normalize_anchors(anchors)
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

    latest_anchor_date = latest_anchor["date"]
    balances = {}
    for date_str in date_strs:
        if date_str <= latest_anchor_date:
            if date_str in backward_balances:
                balances[date_str] = backward_balances[date_str]
        elif date_str in forward_balances:
            balances[date_str] = forward_balances[date_str]

    return balances, deltas, normalized_anchors
