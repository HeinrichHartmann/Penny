"""SQL query builders for dashboard endpoints.

Each public function returns (sql, params) tuple for a specific endpoint.
Internal helpers handle common patterns like WHERE clause construction.
"""



# =============================================================================
# INTERNAL HELPERS
# =============================================================================


def _where(
    params: list,
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
    tab: str | None = None,
    prefix: str = "",
) -> str:
    """Build WHERE clause for common filters.

    Args:
        params: List to append parameter values to (mutated in place)
        from_date: Start date filter (inclusive)
        to_date: End date filter (inclusive)
        accounts: Comma-separated account IDs
        category: Category prefix filter
        q: Search text (matches raw_buchungstext or payee)
        tab: "expense" or "income" to filter by amount sign
        prefix: Table prefix for column names (e.g., "t.")

    Returns:
        WHERE clause string (including "WHERE" keyword), or empty string
    """
    p = prefix
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
            placeholders = ",".join("?" * len(account_list))
            conditions.append(f"{p}account_id IN ({placeholders})")
            params.extend(int(a) for a in account_list)
        else:
            conditions.append("1 = 0")

    if category:
        conditions.append(f"{p}category LIKE ?")
        params.append(f"{category}%")

    if q:
        conditions.append(
            f"COALESCE(NULLIF({p}raw_buchungstext, ''), COALESCE({p}payee, ''), '') LIKE ?"
        )
        params.append(f"%{q}%")

    if tab == "expense":
        conditions.append(f"{p}amount_cents < 0")
    elif tab == "income":
        conditions.append(f"{p}amount_cents > 0")

    if conditions:
        return " WHERE " + " AND ".join(conditions)
    return ""


def _where_and(where_clause: str, condition: str) -> str:
    """Append an additional condition to a WHERE clause."""
    if where_clause:
        return f"{where_clause} AND {condition}"
    return f" WHERE {condition}"


# =============================================================================
# PUBLIC QUERY BUILDERS
# =============================================================================


def categories_query(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    """Query for /api/categories endpoint.

    Returns distinct category paths for the current filter selection.
    """
    params: list = []
    where = _where(params, from_date=from_date, to_date=to_date, accounts=accounts, q=q)
    where = _where_and(where, "category IS NOT NULL AND category != ''")

    sql = f"SELECT DISTINCT category FROM transactions{where} ORDER BY category"
    return sql, params


def summary_query(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    """Query for /api/summary endpoint.

    Returns amount_cents for expense/income aggregation.
    """
    params: list = []
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
    )

    sql = f"SELECT amount_cents FROM transactions{where}"
    return sql, params


def tree_query(
    *,
    tab: str = "expense",
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    """Query for /api/tree endpoint.

    Returns category, payee, amount_cents for treemap construction.
    """
    params: list = []
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
        tab=tab,
    )

    sql = f"SELECT category, payee, amount_cents FROM transactions{where}"
    return sql, params


def pivot_query(
    *,
    tab: str = "expense",
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    """Query for /api/pivot endpoint.

    Returns category, amount_cents for pivot table aggregation.
    """
    params: list = []
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
        tab=tab,
    )

    sql = f"SELECT category, amount_cents FROM transactions{where}"
    return sql, params


def cashflow_query(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    """Query for /api/cashflow endpoint.

    Returns category, amount_cents for Sankey diagram.
    """
    params: list = []
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
    )

    sql = f"SELECT category, amount_cents FROM transactions{where}"
    return sql, params


def breakout_query(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    """Query for /api/breakout endpoint.

    Returns date, category, amount_cents for time-series breakout.
    """
    params: list = []
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
    )

    sql = f"SELECT date, category, amount_cents FROM transactions{where}"
    return sql, params


def report_query(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
) -> tuple[str, list]:
    """Query for /api/report endpoint.

    Returns date, account_id, category, amount_cents for text report.
    """
    params: list = []
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
    )

    sql = f"SELECT date, account_id, category, amount_cents FROM transactions{where}"
    return sql, params
