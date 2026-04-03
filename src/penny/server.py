"""FastAPI web server for Penny."""

from pathlib import Path
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional

app = FastAPI(title="Penny")

# Get the static directory path
STATIC_DIR = Path(__file__).parent / "static"

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Mock Data ────────────────────────────────────────────────────────────────

MOCK_ACCOUNTS = ["private", "shared"]
MOCK_MIN_DATE = "2023-01-01"
MOCK_MAX_DATE = "2024-12-31"

MOCK_TRANSACTIONS = [
    {
        "fp": "abc123",
        "booking_date": "2024-03-15",
        "account": "private",
        "description": "REWE SAGT DANKE",
        "merchant": "REWE",
        "category": "food/groceries",
        "amount_cents": -4523,
    },
    {
        "fp": "def456",
        "booking_date": "2024-03-14",
        "account": "private",
        "description": "GEHALT MAERZ",
        "merchant": "Employer",
        "category": "salary",
        "amount_cents": 350000,
    },
    {
        "fp": "ghi789",
        "booking_date": "2024-03-13",
        "account": "shared",
        "description": "AMAZON EU",
        "merchant": "Amazon",
        "category": "shopping/online",
        "amount_cents": -2999,
    },
    {
        "fp": "jkl012",
        "booking_date": "2024-03-12",
        "account": "private",
        "description": "SHELL TANKSTELLE",
        "merchant": "Shell",
        "category": "transport/fuel",
        "amount_cents": -6500,
    },
    {
        "fp": "mno345",
        "booking_date": "2024-03-11",
        "account": "private",
        "description": "NETFLIX",
        "merchant": "Netflix",
        "category": "subscriptions/streaming",
        "amount_cents": -1299,
    },
]


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
    return {
        "accounts": MOCK_ACCOUNTS,
        "min_date": MOCK_MIN_DATE,
        "max_date": MOCK_MAX_DATE,
    }


@app.get("/api/summary")
async def summary(
    from_date: str = Query(None, alias="from"),
    to_date: str = Query(None, alias="to"),
    accounts: str = Query(""),
    neutralize: bool = Query(True),
):
    """Return expense/income summary."""
    # Filter mock transactions
    expenses = [t for t in MOCK_TRANSACTIONS if t["amount_cents"] < 0]
    income = [t for t in MOCK_TRANSACTIONS if t["amount_cents"] > 0]

    expense_total = sum(t["amount_cents"] for t in expenses)
    income_total = sum(t["amount_cents"] for t in income)

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
    # Build mock tree structure
    if tab == "income":
        return {
            "name": "root",
            "children": [
                {
                    "name": "salary",
                    "value": 350000,
                    "children": [
                        {"name": "(uncategorized)", "value": 350000, "children": []}
                    ]
                }
            ]
        }

    return {
        "name": "root",
        "children": [
            {
                "name": "food",
                "value": 4523,
                "children": [
                    {"name": "groceries", "value": 4523, "children": [
                        {"name": "REWE", "value": 4523}
                    ]}
                ]
            },
            {
                "name": "shopping",
                "value": 2999,
                "children": [
                    {"name": "online", "value": 2999, "children": [
                        {"name": "Amazon", "value": 2999}
                    ]}
                ]
            },
            {
                "name": "transport",
                "value": 6500,
                "children": [
                    {"name": "fuel", "value": 6500, "children": [
                        {"name": "Shell", "value": 6500}
                    ]}
                ]
            },
            {
                "name": "subscriptions",
                "value": 1299,
                "children": [
                    {"name": "streaming", "value": 1299, "children": [
                        {"name": "Netflix", "value": 1299}
                    ]}
                ]
            },
        ]
    }


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
    if tab == "income":
        return {
            "count": 1,
            "total_cents": 350000,
            "categories": [
                {
                    "category": "salary",
                    "txn_count": 1,
                    "share": 1.0,
                    "total_cents": 350000,
                    "weekly_avg_cents": 87500,
                    "monthly_avg_cents": 350000,
                    "yearly_avg_cents": 4200000,
                }
            ]
        }

    total = 4523 + 2999 + 6500 + 1299
    categories = [
        {"category": "transport", "txn_count": 1, "total_cents": 6500},
        {"category": "food", "txn_count": 1, "total_cents": 4523},
        {"category": "shopping", "txn_count": 1, "total_cents": 2999},
        {"category": "subscriptions", "txn_count": 1, "total_cents": 1299},
    ]

    for cat in categories:
        cat["share"] = cat["total_cents"] / total
        cat["weekly_avg_cents"] = cat["total_cents"] // 4
        cat["monthly_avg_cents"] = cat["total_cents"]
        cat["yearly_avg_cents"] = cat["total_cents"] * 12

    return {
        "count": 4,
        "total_cents": total,
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
    txns = MOCK_TRANSACTIONS.copy()

    # Filter by tab (expense/income)
    if tab == "expense":
        txns = [t for t in txns if t["amount_cents"] < 0]
    elif tab == "income":
        txns = [t for t in txns if t["amount_cents"] > 0]

    # Filter by category
    if category:
        txns = [t for t in txns if t["category"].startswith(category)]

    # Filter by search query
    if q:
        q_lower = q.lower()
        txns = [t for t in txns if q_lower in t["description"].lower()
                or q_lower in t["merchant"].lower()
                or q_lower in t["category"].lower()]

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
