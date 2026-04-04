"""FastAPI web server for Penny."""

from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import sqlite3
from collections import defaultdict
from pydantic import BaseModel

from penny.accounts.storage import default_db_path, AccountStorage
from penny.accounts.models import Account
from penny.accounts.registry import AccountRegistry
from penny.import_.detection import match_file, DetectionError
from penny.transactions.storage import TransactionStorage
from penny.classify.engine import load_rules, LoadedRuleset

app = FastAPI(title="Penny")

# Frontend paths
STATIC_DIR = Path(__file__).parent / "static"
FRONTEND_DIST_DIR = STATIC_DIR / "dist"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"

# Mount frontend asset directories
app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets", check_dir=False), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")

# Database path - use same path as CLI (supports PENNY_DATA_DIR env var)
DB_PATH = default_db_path()

def get_db():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Helper Functions ────────────────────────────────────────────────────────

def apply_filters(query, params, from_date=None, to_date=None, accounts=None, neutralize=True, category=None, q=None, table_prefix=""):
    """Apply common filters to a query.

    Schema mapping (new schema):
    - date (was booking_date)
    - account_id (was account, now integer FK)
    - payee (was description/merchant)
    - category (unchanged)
    - neutralization: skipped for now (show all transactions)

    Args:
        table_prefix: Prefix for column names in JOINed queries (e.g., "t.")
    """
    p = table_prefix  # shorthand
    conditions = []

    if from_date:
        conditions.append(f"{p}date >= ?")
        params.append(from_date)

    if to_date:
        conditions.append(f"{p}date <= ?")
        params.append(to_date)

    if accounts is not None:
        account_list = [a for a in accounts.split(',') if a]
        if account_list:
            # Account IDs are now integers
            placeholders = ','.join('?' * len(account_list))
            conditions.append(f"{p}account_id IN ({placeholders})")
            params.extend([int(a) for a in account_list])
        else:
            conditions.append("1 = 0")

    # Neutralization filter skipped for now (per design decision)
    # Future: add neutralization support via classification

    if category:
        conditions.append(f"{p}category LIKE ?")
        params.append(f"{category}%")

    if q:
        # Search against concatenated row (all text fields)
        conditions.append(
            f"(COALESCE({p}payee,'') || ' ' || COALESCE({p}memo,'') || ' ' || "
            f"COALESCE({p}category,'') || ' ' || COALESCE({p}raw_buchungstext,'') || ' ' || "
            f"COALESCE({p}reference,'') || ' ' || COALESCE({p}transaction_type,'')) LIKE ?"
        )
        params.append(f"%{q}%")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    return query


def format_currency(cents: int) -> str:
    """Format cents as EUR using German separators."""
    amount = abs(cents) / 100
    formatted = f"{amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    sign = "-" if cents < 0 else ""
    return f"{sign}{formatted} €"


def parse_date(value: str) -> datetime.date:
    """Parse date from ISO text."""
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
    date = parse_date(booking_date)
    if granularity == "day":
        return date.isoformat()
    if granularity == "week":
        iso_year, iso_week, _ = date.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return f"{date.year}-{date.month:02d}"


def period_label(key: str, granularity: str) -> str:
    """Return a human-friendly period label."""
    if granularity == "day":
        date = parse_date(key)
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


# ── Accounts API ─────────────────────────────────────────────────────────────

def _account_to_dict(account: Account, transaction_count: int = 0) -> dict:
    """Convert Account model to JSON-serializable dict."""
    return {
        "id": account.id,
        "bank": account.bank,
        "display_name": account.display_name,
        "iban": account.iban,
        "holder": account.holder,
        "notes": account.notes,
        "balance_cents": account.balance_cents,
        "balance_date": account.balance_date.isoformat() if account.balance_date else None,
        "subaccounts": list(account.subaccounts.keys()),
        "transaction_count": transaction_count,
        "label": account.display_name or f"{account.bank} #{account.id}",
    }


@app.get("/api/accounts")
async def list_accounts(include_hidden: bool = Query(False)):
    """List all bank accounts."""
    storage = AccountStorage()
    accounts = storage.list_accounts(include_hidden=include_hidden)

    # Get transaction counts per account
    conn = get_db()
    cursor = conn.cursor()
    counts = {
        row[0]: row[1]
        for row in cursor.execute(
            "SELECT account_id, COUNT(*) FROM transactions GROUP BY account_id"
        ).fetchall()
    }
    conn.close()

    return {
        "accounts": [
            _account_to_dict(account, counts.get(account.id, 0))
            for account in accounts
        ]
    }


@app.get("/api/accounts/{account_id}")
async def get_account(account_id: int):
    """Get a single account by ID."""
    storage = AccountStorage()
    account = storage.get_account(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Get transaction count
    conn = get_db()
    cursor = conn.cursor()
    count = cursor.execute(
        "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
    ).fetchone()[0]
    conn.close()

    return _account_to_dict(account, count)


@app.patch("/api/accounts/{account_id}")
async def update_account(
    account_id: int,
    display_name: Optional[str] = None,
    iban: Optional[str] = None,
    holder: Optional[str] = None,
    notes: Optional[str] = None,
):
    """Update account metadata."""
    storage = AccountStorage()
    account = storage.get_account(account_id)

    if account is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    # Update via direct SQL (AccountStorage doesn't have update method yet)
    conn = get_db()
    cursor = conn.cursor()

    updates = []
    params = []
    if display_name is not None:
        updates.append("display_name = ?")
        params.append(display_name)
    if iban is not None:
        updates.append("iban = ?")
        params.append(iban)
    if holder is not None:
        updates.append("holder = ?")
        params.append(holder)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)

    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(account_id)

        cursor.execute(
            f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()

    conn.close()

    # Return updated account
    return await get_account(account_id)


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    """Soft-delete an account (hide it)."""
    storage = AccountStorage()
    if not storage.soft_delete_account(account_id):
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    return {"status": "deleted", "account_id": account_id}


# ── Rules API ────────────────────────────────────────────────────────────────

def get_rules_path() -> Path:
    """Get the rules file path in the XDG data directory."""
    # Always use the XDG data directory (same as penny.db)
    data_dir = default_db_path().parent
    return data_dir / "rules.py"


def get_default_rules_template() -> str:
    """Read the default rules template from the package."""
    import importlib.resources
    return importlib.resources.files("penny").joinpath("default_rules.py").read_text(encoding="utf-8")


@app.get("/api/rules")
async def get_rules():
    """Get the current rules file content and path."""
    rules_path = get_rules_path()

    if not rules_path.exists():
        # Create minimal template
        rules_path.parent.mkdir(parents=True, exist_ok=True)
        rules_path.write_text(get_default_rules_template(), encoding="utf-8")
        return {
            "path": str(rules_path),
            "directory": str(rules_path.parent),
            "exists": True,
            "content": get_default_rules_template(),
            "created": True,
        }

    try:
        content = rules_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read rules file: {e}")

    return {
        "path": str(rules_path),
        "directory": str(rules_path.parent),
        "exists": True,
        "content": content,
    }


class RulesUpdate(BaseModel):
    content: str


@app.put("/api/rules")
async def save_rules(update: RulesUpdate):
    """Save the rules file content."""
    rules_path = get_rules_path()

    # Ensure directory exists
    rules_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        rules_path.write_text(update.content, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rules file: {e}")

    return {
        "status": "saved",
        "path": str(rules_path),
    }


@app.post("/api/rules/run")
async def run_rules():
    """Run classification rules on all transactions.

    Returns stats and any errors encountered during rule loading/execution.
    """
    import traceback
    from collections import Counter

    rules_path = get_rules_path()
    logs: list[dict] = []
    start_time = datetime.now()

    def log(level: str, message: str, **extra):
        logs.append({
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **extra,
        })

    # Check if rules file exists
    if not rules_path.exists():
        log("error", f"Rules file not found: {rules_path}")
        return {
            "status": "error",
            "logs": logs,
            "stats": None,
        }

    # Load rules
    ruleset: LoadedRuleset | None = None
    try:
        log("info", f"Loading rules from {rules_path}")
        ruleset = load_rules(rules_path)
        log("info", f"Loaded {len(ruleset.rules)} rules")
        for rule in ruleset.rules:
            log("debug", f"  - {rule.name} → {rule.category}")
    except SyntaxError as e:
        log("error", f"Syntax error in rules file: {e.msg}", line=e.lineno, offset=e.offset)
        return {
            "status": "error",
            "logs": logs,
            "stats": None,
        }
    except Exception as e:
        log("error", f"Failed to load rules: {e}", traceback=traceback.format_exc())
        return {
            "status": "error",
            "logs": logs,
            "stats": None,
        }

    # Get all transactions
    tx_storage = TransactionStorage()
    transactions = tx_storage.list_transactions(limit=None)
    log("info", f"Processing {len(transactions)} transactions")

    # Run classification
    decisions = []
    category_counts: Counter[str] = Counter()
    unmatched_transactions = []
    errors_during_classification = []

    for tx in transactions:
        try:
            decision = ruleset.classify(tx)
            if decision:
                decisions.append(decision)
                category_counts[decision.category] += 1
            else:
                unmatched_transactions.append(tx)
        except Exception as e:
            errors_during_classification.append({
                "transaction": tx.fingerprint[:12],
                "payee": tx.payee,
                "error": str(e),
            })

    # Apply classifications to database
    matched_count, _ = tx_storage.apply_classifications(decisions)

    # Log classification errors
    if errors_during_classification:
        log("warning", f"{len(errors_during_classification)} errors during classification")
        for err in errors_during_classification[:10]:  # Show first 10
            log("error", f"Error classifying {err['payee']}: {err['error']}")

    # Log category breakdown
    log("info", f"Matched: {matched_count}, Unmatched: {len(unmatched_transactions)}")
    for category, count in sorted(category_counts.items()):
        log("info", f"  {category}: {count}")

    # Log largest unmatched transactions (top 30 by absolute amount)
    if unmatched_transactions:
        log("warning", f"Top unmatched transactions (by amount):")
        sorted_unmatched = sorted(
            unmatched_transactions,
            key=lambda t: abs(t.amount_cents),
            reverse=True,
        )[:30]
        for tx in sorted_unmatched:
            amount_eur = tx.amount_cents / 100
            log("warning", f"  {amount_eur:>10.2f} € | {tx.date} | {tx.payee[:40]}")

    elapsed = (datetime.now() - start_time).total_seconds()
    log("info", f"Classification completed in {elapsed:.2f}s")

    return {
        "status": "success",
        "logs": logs,
        "stats": {
            "rules_count": len(ruleset.rules),
            "transactions_count": len(transactions),
            "matched_count": matched_count,
            "unmatched_count": len(unmatched_transactions),
            "categories": [
                {"category": cat, "count": count}
                for cat, count in sorted(category_counts.items())
            ],
            "elapsed_seconds": elapsed,
        },
    }


# ── Import API ───────────────────────────────────────────────────────────────

@app.post("/api/import")
async def import_csv(file: UploadFile = File(...)):
    """Import transactions from a CSV file.

    This endpoint mirrors the CLI `penny import` command:
    1. Detect the bank format from filename and content
    2. Reconcile or create the bank account
    3. Parse transactions
    4. Store with deduplication
    """
    # Read file content
    content_bytes = await file.read()

    # Try UTF-8 first, fall back to CP1252 (common for German bank CSVs)
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content = content_bytes.decode("cp1252")

    filename = file.filename or "upload.csv"

    # Detect parser
    try:
        parser = match_file(filename, content)
    except DetectionError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not detect CSV format: {e}",
        )

    # Detect account info
    detection = parser.detect(filename, content)

    # Reconcile account (find existing or create new)
    registry = AccountRegistry(AccountStorage())
    try:
        account = registry.reconcile(detection)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Account reconciliation failed: {e}",
        )

    # Parse transactions
    parsed_transactions = parser.parse(filename, content, account_id=account.id)

    # Store transactions with deduplication
    tx_storage = TransactionStorage()
    new_count, duplicate_count = tx_storage.store_transactions(
        parsed_transactions,
        source_file=filename,
    )

    # Build section summary
    from collections import Counter
    section_counts = Counter(tx.subaccount_type for tx in parsed_transactions)

    return {
        "status": "success",
        "filename": filename,
        "parser": detection.parser_name,
        "account": {
            "id": account.id,
            "bank": account.bank,
            "display_name": account.display_name,
            "label": account.display_name or f"{account.bank} #{account.id}",
            "is_new": account.created_at == account.updated_at,  # New if timestamps match
        },
        "sections": [
            {"type": section, "count": count}
            for section, count in sorted(section_counts.items())
        ],
        "transactions": {
            "new": new_count,
            "duplicates": duplicate_count,
            "total_parsed": len(parsed_transactions),
        },
    }


@app.get("/api/meta")
async def meta():
    """Return metadata about available data."""
    conn = get_db()
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
    query = "SELECT category, payee, amount_cents FROM transactions"
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
    query = "SELECT date, category, amount_cents FROM transactions"
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
    query = "SELECT date, account_id, category, amount_cents FROM transactions"
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
    account_label = ", ".join(a for a in (accounts or "").split(",") if a) or "all"
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
    # Join with accounts and account_identifiers to get resolved names
    query = """
        SELECT t.fingerprint, t.date, t.account_id, t.payee, t.memo, t.category,
               t.amount_cents, t.raw_buchungstext, t.subaccount_type,
               COALESCE(a.display_name, a.bank || ' #' || a.id) as account_name,
               ai.identifier_value as account_number
        FROM transactions t
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN account_identifiers ai ON t.account_id = ai.account_id
            AND ai.identifier_type = 'bank_account_number'
    """
    query = apply_filters(query, params, from_date, to_date, accounts, neutralize, category, q, table_prefix="t.")

    # Filter by tab (expense/income)
    if tab == "expense":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "t.amount_cents < 0"
    elif tab == "income":
        query += " AND " if " WHERE " in query else " WHERE "
        query += "t.amount_cents > 0"

    query += " ORDER BY t.date DESC"

    rows = cursor.execute(query, params).fetchall()
    conn.close()

    # Map to frontend-compatible format (no account_id exposed)
    txns = [
        {
            "fp": row[0],  # fingerprint
            "booking_date": row[1],  # date
            "account": row[9] or f"Account #{row[2]}",  # account_name
            "account_number": row[10] or "",  # bank account number
            "subaccount": row[8] or "",  # subaccount_type
            "description": row[3],  # payee
            "merchant": row[3] or "",  # payee (for compatibility)
            "category": row[5] or "uncategorized",
            "amount_cents": row[6],
            "raw_description": row[7] or "",  # raw_buchungstext
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
