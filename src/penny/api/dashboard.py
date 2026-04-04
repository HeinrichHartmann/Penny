"""Dashboard API router - analytics and visualization endpoints."""

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from penny.api.helpers import (
    category_bucket,
    period_key,
    period_label,
    roll_up_top_buckets,
    sort_period_keys,
)
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
from penny.vault import LogManager, VaultConfig
from penny.vault.manifests import BalanceSnapshotManifest

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
    date_range = cursor.execute("SELECT MIN(date), MAX(date) FROM transactions").fetchone()

    conn.close()

    return {
        "accounts": accounts,
        "min_date": date_range[0] if date_range[0] else "2024-01-01",
        "max_date": date_range[1] if date_range[1] else "2026-12-31",
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
    """Return account value history and transaction volume over time.

    Reconstructs historical account value from:
    1. Balance snapshots recorded in the vault
    2. Transaction history from the database

    Returns time-series data for visualization.
    """
    account_ids = _parse_account_ids(accounts)
    if not account_ids:
        return {"error": "No accounts specified"}

    # Get all balance snapshots from the vault log
    config = VaultConfig()
    log_manager = LogManager(config)
    balance_snapshots = []

    for entry in log_manager.iter_entries():
        manifest = entry.read_manifest()
        if isinstance(manifest, BalanceSnapshotManifest):
            if manifest.account_id in account_ids:
                balance_snapshots.append({
                    "account_id": manifest.account_id,
                    "date": manifest.snapshot_date,
                    "balance_cents": manifest.balance_cents,
                    "subaccount_type": manifest.subaccount_type,
                    "note": manifest.note,
                })

    # Sort balance snapshots by date
    balance_snapshots.sort(key=lambda x: x["date"])

    # Get all transactions for these accounts
    conn = connect()
    cursor = conn.cursor()

    account_id_placeholders = ",".join("?" * len(account_ids))
    base_query = f"""
        SELECT date, account_id, subaccount_type, amount_cents
        FROM transactions
        WHERE account_id IN ({account_id_placeholders})
    """

    params = list(account_ids)

    if from_date:
        base_query += " AND date >= ?"
        params.append(from_date)

    if to_date:
        base_query += " AND date <= ?"
        params.append(to_date)

    base_query += " ORDER BY date"

    transactions = cursor.execute(base_query, params).fetchall()
    conn.close()

    # Build time series data
    # Group transactions by date
    txn_by_date = defaultdict(lambda: {"total_cents": 0, "count": 0})

    for row in transactions:
        txn_date = row[0]
        amount = row[3]
        txn_by_date[txn_date]["total_cents"] += amount
        txn_by_date[txn_date]["count"] += 1

    # Build account value time series
    # Strategy: Start from the most recent balance snapshot and work backwards/forwards
    value_points = []

    if balance_snapshots:
        # Use the most recent snapshot as anchor
        latest_snapshot = balance_snapshots[-1]
        anchor_date = latest_snapshot["date"]
        anchor_balance = latest_snapshot["balance_cents"]

        # Calculate balance at each date by adding/subtracting transactions
        all_dates = sorted(set(txn["date"] for txn in transactions) | {s["date"] for s in balance_snapshots})

        # Filter dates if needed
        if from_date:
            all_dates = [d for d in all_dates if d >= from_date]
        if to_date:
            all_dates = [d for d in all_dates if d <= to_date]

        # Build cumulative transaction totals from anchor date
        cumulative_before_anchor = 0
        cumulative_after_anchor = 0

        for txn_date in sorted(txn_by_date.keys()):
            if txn_date < anchor_date:
                cumulative_before_anchor += txn_by_date[txn_date]["total_cents"]
            elif txn_date > anchor_date:
                cumulative_after_anchor += txn_by_date[txn_date]["total_cents"]

        # Calculate balance at each date
        for d in all_dates:
            if d == anchor_date:
                balance = anchor_balance
            elif d < anchor_date:
                # Subtract transactions between this date and anchor
                txns_between = sum(
                    txn_by_date[td]["total_cents"]
                    for td in txn_by_date.keys()
                    if d < td <= anchor_date
                )
                balance = anchor_balance - txns_between
            else:  # d > anchor_date
                # Add transactions between anchor and this date
                txns_between = sum(
                    txn_by_date[td]["total_cents"]
                    for td in txn_by_date.keys()
                    if anchor_date < td <= d
                )
                balance = anchor_balance + txns_between

            value_points.append({
                "date": d,
                "balance_cents": balance,
                "is_snapshot": d in [s["date"] for s in balance_snapshots],
            })
    else:
        # No balance snapshots - just show cumulative transaction flow
        cumulative = 0
        for d in sorted(txn_by_date.keys()):
            cumulative += txn_by_date[d]["total_cents"]
            value_points.append({
                "date": d,
                "balance_cents": cumulative,
                "is_snapshot": False,
            })

    # Build transaction volume data
    volume_points = [
        {
            "date": d,
            "transaction_count": txn_by_date[d]["count"],
            "inflow_cents": sum(row[3] for row in transactions if row[0] == d and row[3] > 0),
            "outflow_cents": abs(sum(row[3] for row in transactions if row[0] == d and row[3] < 0)),
        }
        for d in sorted(txn_by_date.keys())
    ]

    return {
        "account_ids": list(account_ids),
        "balance_snapshots": balance_snapshots,
        "value_points": value_points,
        "volume_points": volume_points,
    }
