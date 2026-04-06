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


def _visible_accounts_condition(prefix: str = "") -> str:
    """Filter transaction rows to visible accounts only."""
    return (
        "EXISTS ("
        "SELECT 1 FROM accounts visible_accounts "
        f"WHERE visible_accounts.id = {prefix}account_id "
        "AND visible_accounts.hidden = 0"
        ")"
    )


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
    where = _where_and(where, _visible_accounts_condition())
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
    neutralize: bool = True,
) -> tuple[str, list]:
    """Query for /api/summary endpoint.

    Returns amount_cents for expense/income aggregation.
    When neutralize=True, groups by group_id to net out transfers.
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
    where = _where_and(where, _visible_accounts_condition())

    if neutralize:
        sql = f"""
            SELECT SUM(amount_cents) as amount_cents
            FROM transactions{where}
            GROUP BY group_id
            HAVING SUM(amount_cents) != 0
        """
    else:
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
    neutralize: bool = True,
) -> tuple[str, list]:
    """Query for /api/tree endpoint.

    Returns category, payee, amount_cents for treemap construction.
    When neutralize=True, groups by group_id to net out transfers.
    """
    params: list = []
    # Don't apply tab filter in base query when neutralizing - filter after grouping
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
        tab=None if neutralize else tab,
    )
    where = _where_and(where, _visible_accounts_condition())

    if neutralize:
        having = (
            "HAVING SUM(amount_cents) < 0" if tab == "expense" else "HAVING SUM(amount_cents) > 0"
        )
        sql = f"""
            SELECT MAX(category) as category, MAX(payee) as payee, SUM(amount_cents) as amount_cents
            FROM transactions{where}
            GROUP BY group_id
            {having}
        """
    else:
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
    neutralize: bool = True,
) -> tuple[str, list]:
    """Query for /api/pivot endpoint.

    Returns category, amount_cents for pivot table aggregation.
    When neutralize=True, groups by group_id to net out transfers.
    """
    params: list = []
    where = _where(
        params,
        from_date=from_date,
        to_date=to_date,
        accounts=accounts,
        category=category,
        q=q,
        tab=None if neutralize else tab,
    )
    where = _where_and(where, _visible_accounts_condition())

    if neutralize:
        having = (
            "HAVING SUM(amount_cents) < 0" if tab == "expense" else "HAVING SUM(amount_cents) > 0"
        )
        sql = f"""
            SELECT MAX(category) as category, SUM(amount_cents) as amount_cents
            FROM transactions{where}
            GROUP BY group_id
            {having}
        """
    else:
        sql = f"SELECT category, amount_cents FROM transactions{where}"
    return sql, params


def cashflow_query(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
    neutralize: bool = True,
) -> tuple[str, list]:
    """Query for /api/cashflow endpoint.

    Returns category, amount_cents for Sankey diagram.
    When neutralize=True, groups by group_id to net out transfers.
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
    where = _where_and(where, _visible_accounts_condition())

    if neutralize:
        sql = f"""
            SELECT MAX(category) as category, SUM(amount_cents) as amount_cents
            FROM transactions{where}
            GROUP BY group_id
            HAVING SUM(amount_cents) != 0
        """
    else:
        sql = f"SELECT category, amount_cents FROM transactions{where}"
    return sql, params


def breakout_query(
    *,
    from_date: str | None = None,
    to_date: str | None = None,
    accounts: str | None = None,
    category: str | None = None,
    q: str | None = None,
    neutralize: bool = True,
) -> tuple[str, list]:
    """Query for /api/breakout endpoint.

    Returns date, category, amount_cents for time-series breakout.
    When neutralize=True, groups by group_id to net out transfers.
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
    where = _where_and(where, _visible_accounts_condition())

    if neutralize:
        sql = f"""
            SELECT MIN(date) as date, MAX(category) as category, SUM(amount_cents) as amount_cents
            FROM transactions{where}
            GROUP BY group_id
            HAVING SUM(amount_cents) != 0
        """
    else:
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
    where = _where_and(where, _visible_accounts_condition())

    sql = f"SELECT date, account_id, category, amount_cents FROM transactions{where}"
    return sql, params


# =============================================================================
# TRANSACTION QUERIES (from TransactionStorage)
# =============================================================================

# The transactions query uses GROUP BY for uniform handling of grouped and
# standalone transactions. The consolidation_col determines behavior:
#   GROUP BY group_id      → transfer groups collapse to net sums
#   GROUP BY fingerprint   → raw entries remain distinct
#
# INVARIANT: group_id is NEVER NULL. Standalone transactions have
# group_id = fingerprint. This is enforced on insert and by migration.

_TRANSACTIONS_QUERY = """
    SELECT
        MIN(t.fingerprint) as fingerprint,
        MIN(t.account_id) as account_id,
        MIN(t.subaccount_type) as subaccount_type,
        MIN(t.date) as date,
        CASE WHEN COUNT(*) = 1
             THEN MAX(t.payee)
             ELSE 'Transfer (' || COUNT(*) || ')'
        END as payee,
        MAX(t.memo) as memo,
        SUM(t.amount_cents) as amount_cents,
        MIN(t.value_date) as value_date,
        MAX(t.transaction_type) as transaction_type,
        MAX(t.reference) as reference,
        MAX(t.raw_buchungstext) as raw_buchungstext,
        NULL as raw_row,
        MAX(t.category) as category,
        MAX(t.classification_rule) as classification_rule,
        MAX(t.group_id) as group_id,
        COALESCE(MAX(a.display_name), MAX(a.bank) || ' #' || MIN(a.id)) as account_name,
        MAX(ai.identifier_value) as account_number,
        COUNT(*) as entry_count
    FROM transactions t
    LEFT JOIN accounts a ON t.account_id = a.id
    LEFT JOIN account_identifiers ai ON t.account_id = ai.account_id
        AND ai.identifier_type = 'bank_account_number'
    {where_clause}
    GROUP BY {consolidation_col}
    ORDER BY MIN(t.date) DESC, MIN(t.fingerprint) DESC
    {limit_clause}
"""


def list_transactions_query(
    *,
    account_id: int | None = None,
    limit: int | None = 20,
    neutralize: bool = True,
    include_hidden: bool = False,
) -> tuple[str, list]:
    """Query for listing transactions with optional grouping.

    Args:
        account_id: Filter to a specific account
        limit: Max rows to return (None for all)
        neutralize: If True, consolidate transfer groups to net sums.
                    If False, return raw entries.
    """
    consolidation_col = "t.group_id" if neutralize else "t.fingerprint"

    where_clause = ""
    params: list = []
    hidden_clause = "" if include_hidden else "COALESCE(a.hidden, 0) = 0"
    if hidden_clause:
        where_clause = f"WHERE {hidden_clause}"

    if account_id is not None:
        if where_clause:
            where_clause += " AND t.account_id = ?"
        else:
            where_clause = "WHERE t.account_id = ?"
        params.append(account_id)

    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT ?"
        params.append(limit)

    sql = _TRANSACTIONS_QUERY.format(
        consolidation_col=consolidation_col,
        where_clause=where_clause,
        limit_clause=limit_clause,
    )
    return sql, params


def insert_transaction_sql() -> str:
    """SQL for inserting a transaction."""
    return """
        INSERT INTO transactions (
            fingerprint, account_id, subaccount_type, date, payee, memo,
            amount_cents, value_date, transaction_type, reference,
            raw_buchungstext, raw_row, category, classification_rule,
            classified_at, imported_at, source_file, group_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """


def clear_classifications_sql() -> str:
    """SQL to clear all classifications."""
    return """
        UPDATE transactions
        SET category = NULL,
            classification_rule = NULL,
            classified_at = NULL
    """


def update_classification_sql() -> str:
    """SQL to update a single transaction's classification."""
    return """
        UPDATE transactions
        SET category = ?, classification_rule = ?, classified_at = ?
        WHERE fingerprint = ?
    """


def count_uncategorized_sql() -> str:
    """SQL to count transactions without a category."""
    return """
        SELECT COUNT(*)
        FROM transactions
        WHERE category IS NULL OR TRIM(category) = ''
    """


def reset_groups_sql() -> str:
    """SQL to reset all group_ids to fingerprint (standalone)."""
    return "UPDATE transactions SET group_id = fingerprint"


def update_group_sql() -> str:
    """SQL to update a single transaction's group_id."""
    return "UPDATE transactions SET group_id = ? WHERE fingerprint = ?"


def count_grouped_sql() -> str:
    """SQL to count transactions in groups."""
    return "SELECT COUNT(*) FROM transactions WHERE group_id != fingerprint"


def count_standalone_sql() -> str:
    """SQL to count standalone transactions."""
    return "SELECT COUNT(*) FROM transactions WHERE group_id = fingerprint"


def count_transactions_sql(account_id: int | None = None) -> tuple[str, list]:
    """SQL to count transactions."""
    params: list = []
    sql = "SELECT COUNT(*) FROM transactions"
    if account_id is not None:
        sql += " WHERE account_id = ?"
        params.append(account_id)
    return sql, params


# =============================================================================
# ACCOUNT QUERIES
# =============================================================================


def insert_account_sql() -> str:
    """SQL for inserting an account."""
    return """
        INSERT INTO accounts (
            bank, display_name, iban, holder, notes,
            created_at, updated_at, hidden
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """


def insert_account_identifier_sql() -> str:
    """SQL for inserting an account identifier."""
    return """
        INSERT INTO account_identifiers (account_id, identifier_type, identifier_value)
        VALUES (?, 'bank_account_number', ?)
    """


def insert_subaccount_sql() -> str:
    """SQL for inserting a subaccount."""
    return """
        INSERT INTO subaccounts (account_id, type, display_name)
        VALUES (?, ?, ?)
    """


def upsert_subaccount_sql() -> str:
    """SQL for upserting a subaccount."""
    return """
        INSERT OR IGNORE INTO subaccounts (account_id, type, display_name)
        VALUES (?, ?, NULL)
    """


def list_account_ids_sql(include_hidden: bool) -> str:
    """SQL for listing account IDs."""
    sql = "SELECT id FROM accounts"
    if not include_hidden:
        sql += " WHERE hidden = 0"
    sql += " ORDER BY id"
    return sql


def get_account_sql(include_hidden: bool) -> str:
    """SQL for getting an account by ID."""
    sql = "SELECT * FROM accounts WHERE id = ?"
    if not include_hidden:
        sql += " AND hidden = 0"
    return sql


def soft_delete_account_sql() -> str:
    """SQL for soft-deleting an account."""
    return """
        UPDATE accounts
        SET hidden = 1, updated_at = ?
        WHERE id = ? AND hidden = 0
    """


def find_account_by_bank_account_number_sql(include_hidden: bool) -> str:
    """SQL for finding an account by bank and account number."""
    sql = """
        SELECT a.*
        FROM accounts a
        JOIN account_identifiers ai ON ai.account_id = a.id
        WHERE a.bank = ?
          AND ai.identifier_type = 'bank_account_number'
          AND ai.identifier_value = ?
    """
    if not include_hidden:
        sql += " AND a.hidden = 0"
    sql += " ORDER BY a.id LIMIT 1"
    return sql


def get_account_identifiers_sql() -> str:
    """SQL for getting account identifiers."""
    return """
        SELECT identifier_value
        FROM account_identifiers
        WHERE account_id = ? AND identifier_type = 'bank_account_number'
        ORDER BY id
    """


def get_subaccounts_sql() -> str:
    """SQL for getting subaccounts."""
    return """
        SELECT type, display_name
        FROM subaccounts
        WHERE account_id = ?
        ORDER BY type
    """


# =============================================================================
# BALANCE ANCHOR QUERIES
# =============================================================================


def upsert_balance_anchor_sql() -> str:
    """SQL for upserting a balance anchor (one per account per date)."""
    return """
        INSERT INTO balance_anchors (account_id, anchor_date, balance_cents, note, source, ledger_sequence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(account_id, anchor_date) DO UPDATE SET
            balance_cents = excluded.balance_cents,
            note = excluded.note,
            source = excluded.source,
            ledger_sequence = excluded.ledger_sequence
    """


def list_balance_anchors_sql(account_id: int | None = None) -> tuple[str, list]:
    """SQL for listing balance anchors."""
    params: list = []
    sql = """
        SELECT id, account_id, anchor_date, balance_cents, note, source, created_at
        FROM balance_anchors
    """
    if account_id is not None:
        sql += " WHERE account_id = ?"
        params.append(account_id)
    sql += " ORDER BY anchor_date"
    return sql, params


def count_balance_anchors_sql(account_id: int | None = None) -> tuple[str, list]:
    """SQL for counting balance anchors per account."""
    params: list = []
    if account_id is not None:
        sql = "SELECT COUNT(*) FROM balance_anchors WHERE account_id = ?"
        params.append(account_id)
    else:
        sql = """
            SELECT account_id, COUNT(*) as count
            FROM balance_anchors
            GROUP BY account_id
        """
    return sql, params


def get_latest_balance_anchor_sql() -> str:
    """SQL for getting the latest balance anchor for an account."""
    return """
        SELECT id, account_id, anchor_date, balance_cents, note, source, created_at
        FROM balance_anchors
        WHERE account_id = ?
        ORDER BY anchor_date DESC
        LIMIT 1
    """


def delete_balance_anchor_sql() -> str:
    """SQL for deleting a balance anchor."""
    return "DELETE FROM balance_anchors WHERE account_id = ? AND anchor_date = ?"


def get_balance_anchors_by_sequence_sql() -> str:
    """SQL for getting balance anchors created by a specific ledger entry."""
    return """
        SELECT id, account_id, anchor_date, balance_cents, note, source, ledger_sequence, created_at
        FROM balance_anchors
        WHERE ledger_sequence = ?
        ORDER BY anchor_date
    """


def delete_balance_anchors_by_sequence_sql() -> str:
    """SQL for deleting balance anchors created by a specific ledger entry."""
    return "DELETE FROM balance_anchors WHERE ledger_sequence = ?"
