"""FastAPI web server for Penny."""

from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import sqlite3
from collections import defaultdict

app = FastAPI(title="Penny")

# Get the static directory path
STATIC_DIR = Path(__file__).parent / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

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

    if accounts:
        account_list = accounts.split(',')
        placeholders = ','.join('?' * len(account_list))
        conditions.append(f"account IN ({placeholders})")
        params.extend(account_list)

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


# ── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text())


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
    accounts: str = Query(""),
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
    accounts: str = Query(""),
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
    accounts: str = Query(""),
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
    accounts: str = Query(""),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
):
    """Return Sankey diagram data."""
    return {
        "total_expense": 15321,
        "nodes": [
            {"name": "salary"},
            {"name": "Budget"},
            {"name": "food"},
            {"name": "shopping"},
            {"name": "transport"},
            {"name": "subscriptions"},
        ],
        "links": [
            {"source": "salary", "target": "Budget", "value": 350000},
            {"source": "Budget", "target": "food", "value": 4523},
            {"source": "Budget", "target": "shopping", "value": 2999},
            {"source": "Budget", "target": "transport", "value": 6500},
            {"source": "Budget", "target": "subscriptions", "value": 1299},
        ],
    }


@app.get("/api/breakout")
async def breakout(
    granularity: str = Query("month"),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(""),
    neutralize: bool = Query(True),
    category: Optional[str] = Query(None),
):
    """Return time-series breakout data."""
    return {
        "periods": ["2024-01", "2024-02", "2024-03"],
        "labels": ["Jan 2024", "Feb 2024", "Mar 2024"],
        "income_total": 350000,
        "expense_total": 15321,
        "categories": [
            {"name": "salary", "values": [350000, 350000, 350000]},
            {"name": "food", "values": [-4000, -4200, -4523]},
            {"name": "shopping", "values": [-1500, -2000, -2999]},
            {"name": "transport", "values": [-5000, -6000, -6500]},
            {"name": "subscriptions", "values": [-1299, -1299, -1299]},
        ],
    }


@app.get("/api/report", response_class=PlainTextResponse)
async def report(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(""),
    neutralize: bool = Query(True),
):
    """Return plain text financial report."""
    return """
═══════════════════════════════════════════════════════════════════════════════
                              PENNY FINANCE REPORT
═══════════════════════════════════════════════════════════════════════════════

Period: 2024-01-01 to 2024-03-31
Accounts: private, shared

───────────────────────────────────────────────────────────────────────────────
SUMMARY
───────────────────────────────────────────────────────────────────────────────

  Total Income:     3.500,00 €
  Total Expenses:     153,21 €
  ─────────────────────────────
  Net Flow:         3.346,79 €

───────────────────────────────────────────────────────────────────────────────
TOP EXPENSE CATEGORIES
───────────────────────────────────────────────────────────────────────────────

  1. transport          65,00 €   (42%)
  2. food               45,23 €   (30%)
  3. shopping           29,99 €   (20%)
  4. subscriptions      12,99 €    (8%)

───────────────────────────────────────────────────────────────────────────────

Report generated by Penny v0.1.0
"""


@app.get("/api/transactions")
async def transactions(
    tab: str = Query(None),
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(""),
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
