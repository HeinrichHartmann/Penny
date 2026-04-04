"""Shared helper functions for API endpoints."""

import sqlite3
from datetime import datetime
from typing import Optional

from penny.accounts.storage import default_db_path

# Database path - use same path as CLI (supports PENNY_DATA_DIR env var)
DB_PATH = default_db_path()


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def apply_filters(
    query: str,
    params: list,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    neutralize: bool = True,
    category: str | None = None,
    q: str | None = None,
    table_prefix: str = "",
) -> str:
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
        account_list = [a for a in accounts.split(",") if a]
        if account_list:
            # Account IDs are now integers
            placeholders = ",".join("?" * len(account_list))
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
    return f"{sign}{formatted} EUR"


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
