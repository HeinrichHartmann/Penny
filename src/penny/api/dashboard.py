"""Dashboard API router - analytics and visualization endpoints."""

from collections import defaultdict
from datetime import date

import pandas as pd
from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from penny.api.helpers import (
    category_bucket,
    period_key,
    period_label,
    roll_up_top_buckets,
    sort_period_keys,
)
from penny.balance_projection import build_balance_series
from penny.db import connect
from penny.reports import generate_report_text
from penny.sql import (
    breakout_query,
    cashflow_query,
    categories_query,
    pivot_query,
    summary_query,
    tree_query,
)
from penny.transactions import TransactionFilter, list_transactions
from penny.vault.config import VaultConfig
from penny.vault.ledger import Ledger

router = APIRouter(prefix="/api", tags=["dashboard"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_account_ids(value: str | None) -> frozenset[int] | None:
    if value is None:
        return None
    account_ids = {int(account_id) for account_id in value.split(",") if account_id}
    return frozenset(account_ids)


def _visible_account_ids(account_ids: frozenset[int]) -> frozenset[int]:
    if not account_ids:
        return frozenset()

    conn = connect()
    placeholders = ",".join("?" * len(account_ids))
    rows = conn.execute(
        f"SELECT id FROM accounts WHERE hidden = 0 AND id IN ({placeholders})",
        tuple(sorted(account_ids)),
    ).fetchall()
    conn.close()
    return frozenset(int(row[0]) for row in rows)


def _build_transaction_filter(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
    tab: str | None = None,
) -> TransactionFilter:
    return TransactionFilter(
        from_date=_parse_date(from_date),
        to_date=_parse_date(to_date),
        account_ids=_parse_account_ids(accounts),
        category_prefix=category,
        search_query=q,
        tab=tab,
    )


@router.get("/meta")
async def meta():
    """Return metadata about available data."""
    conn = connect()
    cursor = conn.cursor()

    # Get accounts from accounts table
    account_rows = cursor.execute(
        "SELECT id, bank, display_name, iban FROM accounts WHERE hidden = 0 ORDER BY id"
    ).fetchall()
    accounts = [
        {
            "id": row[0],
            "bank": row[1],
            "display_name": row[2],
            "iban": row[3],
            "label": row[2] or f"{row[1]} #{row[0]}",  # Display name or fallback
        }
        for row in account_rows
    ]

    # Get date range from transactions
    date_range = cursor.execute(
        """
        SELECT MIN(t.date), MAX(t.date)
        FROM transactions t
        JOIN accounts a ON a.id = t.account_id
        WHERE a.hidden = 0
        """
    ).fetchone()

    conn.close()

    return {
        "accounts": accounts,
        "min_date": date_range[0],
        "max_date": date_range[1],
    }


@router.get("/categories")
async def categories(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    q: str | None = Query(None),
):
    """Return distinct category paths for the current raw filter selection."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = categories_query(from_date=from_date, to_date=to_date, accounts=accounts, q=q)
    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    return {
        "categories": [row[0] for row in rows],
    }


@router.get("/summary")
async def summary(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    category: str | None = Query(None),
    q: str | None = Query(None),
):
    """Return expense/income summary."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = summary_query(
        from_date=from_date, to_date=to_date, accounts=accounts, category=category, q=q
    )
    transactions = cursor.execute(sql, params).fetchall()
    conn.close()

    expenses = [t[0] for t in transactions if t[0] < 0]
    income = [t[0] for t in transactions if t[0] > 0]

    expense_total = sum(expenses) if expenses else 0
    income_total = sum(income) if income else 0

    return {
        "expense": {
            "total_cents": expense_total,
            "count": len(expenses),
        },
        "income": {
            "total_cents": income_total,
            "count": len(income),
        },
        "net_flow": income_total + expense_total,
    }


@router.get("/tree")
async def tree(
    tab: str = Query("expense"),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    category: str | None = Query(None),
    q: str | None = Query(None),
):
    """Return hierarchical category tree for treemap."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = tree_query(
        tab=tab, from_date=from_date, to_date=to_date, accounts=accounts, category=category, q=q
    )
    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    # Build tree from categories
    tree_data = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for row in rows:
        cat = row[0] or "uncategorized"
        merchant = row[1] or "unknown"
        amount = abs(row[2])

        parts = cat.split("/")
        level1 = parts[0] if parts else "uncategorized"
        level2 = parts[1] if len(parts) > 1 else "(uncategorized)"

        tree_data[level1][level2][merchant] += amount

    # Convert to tree structure
    children = []
    for l1, l2_data in sorted(tree_data.items()):
        l1_value = sum(sum(merchants.values()) for merchants in l2_data.values())
        l2_children = []
        for l2, merchants in sorted(l2_data.items()):
            l2_value = sum(merchants.values())
            l3_children = [
                {"name": m, "value": v}
                for m, v in sorted(merchants.items(), key=lambda x: x[1], reverse=True)
            ]
            l2_children.append({"name": l2, "value": l2_value, "children": l3_children})
        children.append({"name": l1, "value": l1_value, "children": l2_children})

    # Sort by value
    children.sort(key=lambda x: x["value"], reverse=True)

    return {"name": "root", "children": children}


@router.get("/pivot")
async def pivot(
    tab: str = Query("expense"),
    depth: str = Query("1"),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    category: str | None = Query(None),
    q: str | None = Query(None),
):
    """Return pivot table data."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = pivot_query(
        tab=tab, from_date=from_date, to_date=to_date, accounts=accounts, category=category, q=q
    )
    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    # Group by category at specified depth
    depth_int = int(depth) if depth else 1
    cat_data = defaultdict(lambda: {"total": 0, "count": 0})

    for row in rows:
        cat = row[0] or "uncategorized"
        amount = abs(row[1])

        # Extract category at specified depth
        parts = cat.split("/")
        cat_key = "/".join(parts[:depth_int]) if len(parts) >= depth_int else cat

        cat_data[cat_key]["total"] += amount
        cat_data[cat_key]["count"] += 1

    # Calculate totals
    total_cents = sum(c["total"] for c in cat_data.values())
    total_count = sum(c["count"] for c in cat_data.values())

    # Build categories list
    categories = []
    for cat_key, data in sorted(cat_data.items(), key=lambda x: x[1]["total"], reverse=True):
        categories.append(
            {
                "category": cat_key,
                "txn_count": data["count"],
                "share": data["total"] / total_cents if total_cents > 0 else 0,
                "total_cents": data["total"],
                "weekly_avg_cents": data["total"] // 4,
                "monthly_avg_cents": data["total"],
                "yearly_avg_cents": data["total"] * 12,
            }
        )

    return {
        "count": total_count,
        "total_cents": total_cents,
        "categories": categories,
    }


@router.get("/cashflow")
async def cashflow(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    category: str | None = Query(None),
    q: str | None = Query(None),
):
    """Return Sankey diagram data derived from filtered transactions."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = cashflow_query(
        from_date=from_date, to_date=to_date, accounts=accounts, category=category, q=q
    )
    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    income_buckets = defaultdict(int)
    expense_buckets = defaultdict(int)

    for row in rows:
        bucket = category_bucket(row[0], category)
        amount = row[1]
        if amount > 0:
            income_buckets[bucket] += amount
        elif amount < 0:
            expense_buckets[bucket] += abs(amount)

    total_expense = sum(expense_buckets.values())

    visible_income = roll_up_top_buckets(income_buckets, 6, "other income")
    visible_expense = roll_up_top_buckets(expense_buckets, 8, "other expenses")

    def bucket_value(name: str, buckets: dict[str, int], visible_names: list[str]) -> int:
        if name not in visible_names:
            return 0
        if name.startswith("other "):
            return sum(
                value for bucket, value in buckets.items() if bucket not in visible_names[:-1]
            )
        return buckets[name]

    links = []
    for name in visible_income:
        value = bucket_value(name, income_buckets, visible_income)
        if value > 0:
            links.append({"source": f"{name} (in)", "target": "Budget", "value": value})

    for name in visible_expense:
        value = bucket_value(name, expense_buckets, visible_expense)
        if value > 0:
            links.append({"source": "Budget", "target": f"{name} (out)", "value": value})

    return {
        "total_expense": total_expense,
        "nodes": [{"name": link["source"]} for link in links]
        + [{"name": link["target"]} for link in links],
        "links": links,
    }


@router.get("/breakout")
async def breakout(
    granularity: str = Query("month"),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    category: str | None = Query(None),
    q: str | None = Query(None),
):
    """Return time-series breakout data."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = breakout_query(
        from_date=from_date, to_date=to_date, accounts=accounts, category=category, q=q
    )
    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    period_totals = defaultdict(lambda: defaultdict(int))
    bucket_totals = defaultdict(int)
    periods = set()
    income_total = 0
    expense_total = 0

    for row in rows:
        key = period_key(row[0], granularity)
        bucket = category_bucket(row[1], category)
        amount = row[2]
        period_totals[bucket][key] += amount
        bucket_totals[bucket] += abs(amount)
        periods.add(key)
        if amount > 0:
            income_total += amount
        elif amount < 0:
            expense_total += abs(amount)

    ordered_periods = sort_period_keys(list(periods), granularity)
    labels = [period_label(key, granularity) for key in ordered_periods]
    visible_buckets = roll_up_top_buckets(bucket_totals, 8, "other")

    categories = []
    for bucket_name in visible_buckets:
        values = []
        for key in ordered_periods:
            if bucket_name == "other":
                value = sum(
                    totals.get(key, 0)
                    for name, totals in period_totals.items()
                    if name not in visible_buckets[:-1]
                )
            else:
                value = period_totals[bucket_name].get(key, 0)
            values.append(value)
        categories.append({"name": bucket_name, "values": values})

    return {
        "periods": ordered_periods,
        "labels": labels,
        "income_total": income_total,
        "expense_total": expense_total,
        "categories": categories,
    }


@router.get("/report", response_class=PlainTextResponse)
async def report(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    category: str | None = Query(None),
    q: str | None = Query(None),
):
    """Return plain text financial report."""
    filters = _build_transaction_filter(
        from_date=from_date, to_date=to_date, accounts=accounts, category=category, q=q
    )
    return generate_report_text(filters)


@router.get("/transactions")
async def transactions(
    tab: str = Query(None),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
    category: str | None = Query(None),
    q: str | None = Query(None),
):
    """Return filtered transaction list using the shared domain filter logic."""
    filtered = list_transactions(
        filters=_build_transaction_filter(
            from_date=from_date,
            to_date=to_date,
            accounts=accounts,
            category=category,
            q=q,
            tab=tab,
        ),
        limit=None,
        neutralize=neutralize,
    )

    # Map to frontend format
    txns = [
        {
            "fp": tx.fingerprint,
            "booking_date": tx.date.isoformat(),
            "account_id": tx.account_id,
            "account": tx.account_name or f"Account #{tx.account_id}",
            "account_number": tx.account_number or "",
            "subaccount": tx.subaccount_type or "",
            "description": tx.payee,
            "merchant": tx.payee or "",
            "category": tx.category or "uncategorized",
            "amount_cents": tx.amount_cents,
            "raw_description": tx.raw_buchungstext or "",
            "entry_count": tx.entry_count,  # For UI badge on grouped entries
            "group_id": tx.group_id,  # For expandable detail view
        }
        for tx in filtered
    ]

    total_cents = sum(t["amount_cents"] for t in txns)

    return {
        "count": len(txns),
        "total_cents": total_cents,
        "transactions": txns,
    }


@router.get("/account_value_history")
async def account_value_history(
    accounts: str = Query(...),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
):
    """Return account balance history with anchor-based projection.

    Math model:
    1. Get RAW (unneutralized) transactions for full history per account.
    2. Bucket them to a daily saldo (net change per day).
    3. Sort anchors by date and keep only the last-added anchor per day.
    4. Walk anchors backward to detect deltas and fill dates before the first anchor.
    5. Walk anchors forward to build the displayed balance series, resetting to each
       anchor when it is reached.
    """
    # Parse and validate accounts
    account_ids = _parse_account_ids(accounts)
    if not account_ids:
        return {"error": "No accounts specified"}
    account_ids = _visible_account_ids(account_ids)
    if not account_ids:
        return {
            "account_ids": [],
            "balance_snapshots": [],
            "value_points": [],
            "inconsistencies": [],
        }

    # Get all balance snapshots for these accounts (from vault ledger)
    config = VaultConfig()
    if not config.is_initialized():
        config.initialize()
    ledger = Ledger(config.path)
    all_snapshots = []

    for entry in ledger.read_entries():
        if entry.entry_type == "balance":
            # Balance entries have snapshots list in record
            for snapshot in entry.record.get("snapshots", []):
                if snapshot["account_id"] in account_ids:
                    all_snapshots.append(
                        {
                            "account_id": snapshot["account_id"],
                            "date": snapshot["snapshot_date"],
                            "balance_cents": snapshot["balance_cents"],
                        }
                    )

    # Sort snapshots by account and date
    all_snapshots.sort(key=lambda x: (x["account_id"], x["date"]))

    # Get RAW transactions for FULL history (no neutralization, no date filter)
    filters = TransactionFilter(
        account_ids=account_ids,
        # NO from_date/to_date - we need the full history!
    )

    transactions = list_transactions(
        filters=filters,
        limit=None,
        neutralize=False,  # RAW transactions only
    )

    if not transactions:
        return {
            "account_ids": list(account_ids),
            "balance_snapshots": all_snapshots,
            "value_points": [],
            "inconsistencies": [],
        }

    # Build DataFrame and aggregate to DAILY saldo per account
    tx_data = [
        {
            "date": tx.date.isoformat(),
            "account_id": tx.account_id,
            "amount_cents": tx.amount_cents,
        }
        for tx in transactions
    ]
    df = pd.DataFrame(tx_data)

    # Group by account and date, sum amounts to get daily saldo
    daily_saldo = df.groupby(["account_id", "date"])["amount_cents"].sum().reset_index()
    daily_saldo.columns = ["account_id", "date", "saldo"]

    # Create per-account balance histories
    account_balances = {}  # {account_id: {date: balance}}
    inconsistencies = []

    for acc_id in account_ids:
        # Get snapshots for this account
        acc_snapshots = [s for s in all_snapshots if s["account_id"] == acc_id]
        acc_snapshots.sort(key=lambda x: x["date"])

        # Get daily saldo for this account
        acc_saldo = daily_saldo[daily_saldo["account_id"] == acc_id].copy()
        acc_saldo = acc_saldo.set_index("date")["saldo"].to_dict()

        # Get full date range for this account
        acc_df = df[df["account_id"] == acc_id]
        if acc_df.empty:
            continue

        min_date = acc_df["date"].min()
        max_date = acc_df["date"].max()

        # Create full date range (as series)
        date_range = pd.date_range(start=min_date, end=max_date, freq="D")
        date_strs = [d.strftime("%Y-%m-%d") for d in date_range]

        if not acc_snapshots:
            # No anchors - can't compute balances
            continue

        balances, backward_deltas, _normalized_anchors = build_balance_series(
            date_strs,
            acc_saldo,
            acc_snapshots,
        )

        inconsistencies.extend(
            {"account_id": acc_id, **delta}
            for delta in backward_deltas
        )
        account_balances[acc_id] = balances

    # Combine all accounts into total balance per day
    # Get union of all dates
    all_dates = set()
    for balances in account_balances.values():
        all_dates.update(balances.keys())

    all_dates = sorted(all_dates)

    # Calculate total balance per day
    value_points = []
    anchor_dates = {s["date"] for s in all_snapshots}

    for date_str in all_dates:
        total_balance = sum(
            account_balances.get(acc_id, {}).get(date_str, 0) for acc_id in account_ids
        )

        value_points.append(
            {
                "date": date_str,
                "total_balance": total_balance,
                "is_anchor": date_str in anchor_dates,
            }
        )

    # Filter to requested date range (for display only - math uses full range)
    if from_date or to_date:
        from_date_str = from_date if from_date else value_points[0]["date"]
        to_date_str = to_date if to_date else value_points[-1]["date"]
        value_points = [vp for vp in value_points if from_date_str <= vp["date"] <= to_date_str]

    return {
        "account_ids": list(account_ids),
        "balance_snapshots": all_snapshots,
        "value_points": value_points,
        "inconsistencies": inconsistencies,
    }
