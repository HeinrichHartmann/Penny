"""Dashboard API router - analytics and visualization endpoints."""

from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from penny.api.helpers import (
    category_bucket,
    format_currency,
    period_key,
    period_label,
    roll_up_top_buckets,
    sort_period_keys,
)
from penny.db import connect
from penny.sql import (
    breakout_query,
    cashflow_query,
    categories_query,
    pivot_query,
    report_query,
    summary_query,
    tree_query,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


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
        "SELECT MIN(date), MAX(date) FROM transactions"
    ).fetchone()

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
    q: Optional[str] = Query(None),
):
    """Return distinct category paths for the current raw filter selection."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = categories_query(
        from_date=from_date, to_date=to_date, accounts=accounts, q=q
    )
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
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
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
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
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
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
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
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
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
            return sum(value for bucket, value in buckets.items() if bucket not in visible_names[:-1])
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
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
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
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    """Return plain text financial report."""
    conn = connect()
    cursor = conn.cursor()

    sql, params = report_query(
        from_date=from_date, to_date=to_date, accounts=accounts, category=category, q=q
    )
    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    expense_total = sum(abs(row[3]) for row in rows if row[3] < 0)
    income_total = sum(row[3] for row in rows if row[3] > 0)
    net_flow = income_total - expense_total

    expense_categories = defaultdict(int)
    income_categories = defaultdict(int)
    for row in rows:
        bucket = category_bucket(row[2])
        if row[3] < 0:
            expense_categories[bucket] += abs(row[3])
        elif row[3] > 0:
            income_categories[bucket] += row[3]

    top_expenses = sorted(expense_categories.items(), key=lambda item: item[1], reverse=True)[:5]
    top_income = sorted(income_categories.items(), key=lambda item: item[1], reverse=True)[:5]
    account_label = ", ".join(a for a in (accounts or "").split(",") if a) or "all"
    period_lbl = f"{from_date or 'beginning'} to {to_date or 'today'}"

    lines = [
        "=" * 79,
        "                              PENNY FINANCE REPORT",
        "=" * 79,
        "",
        f"Period:   {period_lbl}",
        f"Accounts: {account_label}",
        "",
        "SUMMARY",
        "-" * 7,
        f"  Transactions:    {len(rows)}",
        f"  Total Income:    {format_currency(income_total)}",
        f"  Total Expenses:  {format_currency(expense_total)}",
        f"  Net Flow:        {format_currency(net_flow)}",
    ]

    if top_expenses:
        lines.extend(["", "TOP EXPENSE CATEGORIES", "-" * 22])
        for index, (name, value) in enumerate(top_expenses, start=1):
            share = round((value / expense_total) * 100) if expense_total else 0
            lines.append(f"  {index}. {name:<20} {format_currency(value):>12}  ({share:>2}%)")

    if top_income:
        lines.extend(["", "TOP INCOME CATEGORIES", "-" * 21])
        for index, (name, value) in enumerate(top_income, start=1):
            share = round((value / income_total) * 100) if income_total else 0
            lines.append(f"  {index}. {name:<20} {format_currency(value):>12}  ({share:>2}%)")

    lines.extend(["", "Report generated by Penny v0.1.0"])
    return "\n".join(lines)


@router.get("/transactions")
async def transactions(
    tab: str = Query(None),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    """Return filtered transaction list.

    Uses storage layer for proper GROUP BY when neutralize=True.
    Filtering is done in Python for simplicity.
    """
    from penny.transactions import list_transactions

    all_txns = list_transactions(limit=None, neutralize=neutralize)

    # Parse account IDs filter
    account_ids = None
    if accounts:
        account_ids = {int(a) for a in accounts.split(",") if a}

    # Filter transactions
    filtered = []
    for tx in all_txns:
        # Date filter
        date_str = tx.date.isoformat()
        if from_date and date_str < from_date:
            continue
        if to_date and date_str > to_date:
            continue

        # Account filter
        if account_ids is not None and tx.account_id not in account_ids:
            continue

        # Category filter (prefix match)
        if category:
            if not tx.category or not tx.category.startswith(category):
                continue

        # Search filter
        if q:
            search_text = (tx.raw_buchungstext or tx.payee or "").lower()
            if q.lower() not in search_text:
                continue

        # Tab filter (expense/income) - applied to net amount for groups
        if tab == "expense" and tx.amount_cents >= 0:
            continue
        if tab == "income" and tx.amount_cents <= 0:
            continue

        filtered.append(tx)

    # Sort by date descending, then fingerprint for stability
    filtered.sort(key=lambda tx: (tx.date, tx.fingerprint), reverse=True)

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
