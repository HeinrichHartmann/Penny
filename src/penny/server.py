"""FastAPI web server for Penny."""

from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import sqlite3
from collections import defaultdict

app = FastAPI(title="Penny")

# Frontend paths
STATIC_DIR = Path(__file__).parent / "static"
FRONTEND_DIST_DIR = STATIC_DIR / "dist"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"

# Mount frontend asset directories
app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets", check_dir=False), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")

# Database path - look for demo.db in project root
DB_PATH = Path(__file__).parent.parent.parent / "demo.db"

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Helper Functions ────────────────────────────────────────────────────────

def apply_filters(query, params, from_date=None, to_date=None, accounts=None, neutralize=True, category=None, q=None):
    """Apply common filters to a query."""
    conditions = []

    if from_date:
        conditions.append("booking_date >= ?")
        params.append(from_date)

    if to_date:
        conditions.append("booking_date <= ?")
        params.append(to_date)

    if accounts is not None:
        account_list = [account for account in accounts.split(',') if account]
        if account_list:
            placeholders = ','.join('?' * len(account_list))
            conditions.append(f"account IN ({placeholders})")
            params.extend(account_list)
        else:
            conditions.append("1 = 0")

    if neutralize:
        conditions.append("(neutralization_id IS NULL OR neutralization_id = '')")

    if category:
        conditions.append("category LIKE ?")
        params.append(f"{category}%")

    if q:
        conditions.append("(description LIKE ? OR merchant LIKE ? OR category LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    return query


def format_currency(cents: int) -> str:
    """Format cents as EUR using German separators."""
    amount = abs(cents) / 100
    formatted = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    sign = "-" if cents < 0 else ""
    return f"{sign}{formatted} €"


def parse_booking_date(value: str) -> datetime.date:
    """Parse booking date from ISO text."""
    return datetime.strptime(value, "%Y-%m-%d").date()


def category_bucket(category: Optional[str], selected_category: Optional[str] = None) -> str:
    """Group categories at the first visible level for charts."""
    cat = category or "uncategorized"
    if selected_category:
        prefix = selected_category.rstrip("/")
        if cat == prefix:
            return prefix
        if cat.startswith(f"{prefix}/"):
            child = cat[len(prefix) + 1 :].split("/")[0]
            return f"{prefix}/{child}"
        return cat
    return cat.split("/")[0]


def period_key(booking_date: str, granularity: str) -> str:
    """Return the period key used for breakout grouping."""
    date = parse_booking_date(booking_date)
    if granularity == "day":
        return date.isoformat()
    if granularity == "week":
        iso_year, iso_week, _ = date.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return f"{date.year}-{date.month:02d}"


def period_label(key: str, granularity: str) -> str:
    """Return a human-friendly period label."""
    if granularity == "day":
        date = parse_booking_date(key)
        return date.strftime("%d %b %Y")
    if granularity == "week":
        year, week = key.split("-W")
        return f"W{week} {year}"
    year, month = key.split("-")
    return datetime(int(year), int(month), 1).strftime("%b %Y")


def sort_period_keys(keys: list[str], granularity: str) -> list[str]:
    """Sort breakout periods chronologically."""
    if granularity == "day":
        return sorted(keys)
    if granularity == "week":
        return sorted(keys, key=lambda key: (int(key.split("-W")[0]), int(key.split("-W")[1])))
    return sorted(keys)


def roll_up_top_buckets(bucket_totals: dict[str, int], limit: int, other_label: str) -> list[str]:
    """Keep the largest buckets and collapse the tail into an optional other bucket."""
    ordered = sorted(bucket_totals.items(), key=lambda item: item[1], reverse=True)
    if len(ordered) <= limit:
        return [name for name, _ in ordered]
    return [name for name, _ in ordered[:limit]] + [other_label]


# ── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    if not FRONTEND_INDEX_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend bundle is missing. Run `make frontend-build` before starting Penny.",
        )

    return HTMLResponse(content=FRONTEND_INDEX_PATH.read_text())


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/meta")
async def meta():
    """Return metadata about available data."""
    conn = get_db()
    cursor = conn.cursor()

    # Get distinct accounts
    accounts = [row[0] for row in cursor.execute(
        "SELECT DISTINCT account FROM transactions ORDER BY account"
    ).fetchall()]

    # Get date range
    date_range = cursor.execute(
        "SELECT MIN(booking_date), MAX(booking_date) FROM transactions"
    ).fetchone()

    conn.close()

    return {
        "accounts": accounts,
        "min_date": date_range[0] if date_range[0] else "2024-01-01",
        "max_date": date_range[1] if date_range[1] else "2026-12-31",
    }


@app.get("/api/summary")
async def summary(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
):
    """Return expense/income summary."""
    conn = get_db()
    cursor = conn.cursor()

    params = []
    query = "SELECT amount_cents FROM transactions"
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize)

    transactions = cursor.execute(query, params).fetchall()
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


@app.get("/api/tree")
async def tree(
    tab: str = Query("expense"),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
):
    """Return hierarchical category tree for treemap."""
    conn = get_db()
    cursor = conn.cursor()

    params = []
    query = "SELECT category, merchant, amount_cents FROM transactions"
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize, category)

    # Filter by tab
    if tab == "expense":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "amount_cents < 0"
    elif tab == "income":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "amount_cents > 0"

    rows = cursor.execute(query, params).fetchall()
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
            l3_children = [{"name": m, "value": v} for m, v in sorted(merchants.items(), key=lambda x: x[1], reverse=True)]
            l2_children.append({"name": l2, "value": l2_value, "children": l3_children})
        children.append({"name": l1, "value": l1_value, "children": l2_children})

    # Sort by value
    children.sort(key=lambda x: x["value"], reverse=True)

    return {"name": "root", "children": children}


@app.get("/api/pivot")
async def pivot(
    tab: str = Query("expense"),
    depth: str = Query("1"),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
):
    """Return pivot table data."""
    conn = get_db()
    cursor = conn.cursor()

    params = []
    query = "SELECT category, amount_cents FROM transactions"
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize, category)

    # Filter by tab
    if tab == "expense":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "amount_cents < 0"
    elif tab == "income":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "amount_cents > 0"

    rows = cursor.execute(query, params).fetchall()
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
        categories.append({
            "category": cat_key,
            "txn_count": data["count"],
            "share": data["total"] / total_cents if total_cents > 0 else 0,
            "total_cents": data["total"],
            "weekly_avg_cents": data["total"] // 4,
            "monthly_avg_cents": data["total"],
            "yearly_avg_cents": data["total"] * 12,
        })

    return {
        "count": total_count,
        "total_cents": total_cents,
        "categories": categories,
    }


@app.get("/api/cashflow")
async def cashflow(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
):
    """Return Sankey diagram data derived from filtered transactions."""
    conn = get_db()
    cursor = conn.cursor()

    params = []
    query = "SELECT category, amount_cents FROM transactions"
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize, category)

    rows = cursor.execute(query, params).fetchall()
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
        "nodes": [{"name": link["source"]} for link in links] + [{"name": link["target"]} for link in links],
        "links": links,
    }


@app.get("/api/breakout")
async def breakout(
    granularity: str = Query("month"),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
):
    """Return time-series breakout data."""
    conn = get_db()
    cursor = conn.cursor()

    params = []
    query = "SELECT booking_date, category, amount_cents FROM transactions"
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize, category)

    rows = cursor.execute(query, params).fetchall()
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


@app.get("/api/report", response_class=PlainTextResponse)
async def report(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
):
    """Return plain text financial report."""
    conn = get_db()
    cursor = conn.cursor()

    params = []
    query = "SELECT booking_date, account, category, amount_cents FROM transactions"
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize)
    rows = cursor.execute(query, params).fetchall()
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
    account_label = ", ".join(account for account in (accounts or "").split(",") if account) or "all"
    period_label = f"{from_date or 'beginning'} to {to_date or 'today'}"

    lines = [
        "═══════════════════════════════════════════════════════════════════════════════",
        "                              PENNY FINANCE REPORT",
        "═══════════════════════════════════════════════════════════════════════════════",
        "",
        f"Period:   {period_label}",
        f"Accounts: {account_label}",
        "",
        "SUMMARY",
        "───────",
        f"  Transactions:    {len(rows)}",
        f"  Total Income:    {format_currency(income_total)}",
        f"  Total Expenses:  {format_currency(expense_total)}",
        f"  Net Flow:        {format_currency(net_flow)}",
    ]

    if top_expenses:
        lines.extend(["", "TOP EXPENSE CATEGORIES", "──────────────────────"])
        for index, (name, value) in enumerate(top_expenses, start=1):
            share = round((value / expense_total) * 100) if expense_total else 0
            lines.append(f"  {index}. {name:<20} {format_currency(value):>12}  ({share:>2}%)")

    if top_income:
        lines.extend(["", "TOP INCOME CATEGORIES", "─────────────────────"])
        for index, (name, value) in enumerate(top_income, start=1):
            share = round((value / income_total) * 100) if income_total else 0
            lines.append(f"  {index}. {name:<20} {format_currency(value):>12}  ({share:>2}%)")

    lines.extend(["", "Report generated by Penny v0.1.0"])
    return "\n".join(lines)


@app.get("/api/transactions")
async def transactions(
    tab: str = Query(None),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(None),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
):
    """Return filtered transaction list."""
    conn = get_db()
    cursor = conn.cursor()

    params = []
    query = "SELECT fp, booking_date, account, description, merchant, category, amount_cents FROM transactions"
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize, category, q)

    # Filter by tab (expense/income)
    if tab == "expense":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "amount_cents < 0"
    elif tab == "income":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "amount_cents > 0"

    query += " ORDER BY booking_date DESC"

    rows = cursor.execute(query, params).fetchall()
    conn.close()

    txns = [
        {
            "fp": row[0],
            "booking_date": row[1],
            "account": row[2],
            "description": row[3],
            "merchant": row[4] or "",
            "category": row[5] or "uncategorized",
            "amount_cents": row[6],
        }
        for row in rows
    ]

    total_cents = sum(t["amount_cents"] for t in txns)

    return {
        "count": len(txns),
        "total_cents": total_cents,
        "transactions": txns,
    }


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the uvicorn server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
