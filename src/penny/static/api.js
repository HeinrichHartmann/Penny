/**
 * API service for fetching data from the backend.
 */

/**
 * Build query string from filters.
 * @param {object} filters
 * @returns {string}
 */
export const buildQueryString = (filters) => {
  const p = new URLSearchParams();
  p.set('from', filters.from);
  p.set('to', filters.to);
  p.set('accounts', filters.accounts.join(','));
  p.set('neutralize', filters.neutralize);
  return p.toString();
};

/**
 * Fetch JSON from API with filters.
 * @param {string} path
 * @param {object} filters
 * @returns {Promise<any>}
 */
export const fetchJson = async (path, filters) => {
  const qs = buildQueryString(filters);
  const separator = path.includes('?') ? '&' : '?';
  const resp = await fetch(`${path}${separator}${qs}`);
  return resp.json();
};

/**
 * Fetch metadata.
 * @returns {Promise<{ accounts: object[], min_date: string, max_date: string }>}
 */
export const fetchMeta = async () => {
  const resp = await fetch('/api/meta');
  return resp.json();
};

/**
 * Fetch all accounts.
 * @param {boolean} includeHidden - Include hidden accounts
 * @returns {Promise<{ accounts: object[] }>}
 */
export const fetchAccounts = async (includeHidden = false) => {
  const params = includeHidden ? '?include_hidden=true' : '';
  const resp = await fetch(`/api/accounts${params}`);
  return resp.json();
};

/**
 * Fetch distinct category paths for the current filter selection.
 * @param {object} filters
 * @param {string} searchQuery
 * @returns {Promise<{ categories: string[] }>}
 */
export const fetchCategoryOptions = async (filters, searchQuery = '') => {
  const qs = buildQueryString(filters);
  const qParam = searchQuery ? `&q=${encodeURIComponent(searchQuery)}` : '';
  const resp = await fetch(`/api/categories?${qs}${qParam}`);
  return resp.json();
};

/**
 * Update an account.
 * @param {number} accountId
 * @param {object} updates - { display_name?, iban?, holder?, notes? }
 * @returns {Promise<object>}
 */
export const updateAccount = async (accountId, updates) => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(updates)) {
    if (value !== undefined && value !== null) {
      params.set(key, value);
    }
  }
  const resp = await fetch(`/api/accounts/${accountId}?${params}`, {
    method: 'PATCH',
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Update failed');
  }
  return resp.json();
};

/**
 * Record a balance snapshot for an account.
 * @param {number} accountId
 * @param {object} snapshot - { balance_cents, balance_date, subaccount_type?, note? }
 * @returns {Promise<object>}
 */
export const recordBalanceSnapshot = async (accountId, snapshot) => {
  const resp = await fetch(`/api/accounts/${accountId}/balance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(snapshot),
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Failed to record balance');
  }
  return resp.json();
};

/**
 * Delete (hide) an account.
 * @param {number} accountId
 * @returns {Promise<object>}
 */
export const deleteAccount = async (accountId) => {
  const resp = await fetch(`/api/accounts/${accountId}`, {
    method: 'DELETE',
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Failed to delete account');
  }
  return resp.json();
};

/**
 * Fetch the rules file content and path.
 * @returns {Promise<{ path: string, directory: string, exists: boolean, content: string|null }>}
 */
export const fetchRules = async () => {
  const resp = await fetch('/api/rules');
  return resp.json();
};

/**
 * Save the rules file content.
 * @param {string} content
 * @returns {Promise<object>}
 */
export const saveRules = async (content) => {
  const resp = await fetch('/api/rules', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Save failed');
  }
  return resp.json();
};

/**
 * Run classification rules on all transactions.
 * @returns {Promise<{ status: string, logs: object[], stats: object|null }>}
 */
export const runRules = async () => {
  const resp = await fetch('/api/rules/run', {
    method: 'POST',
  });
  return resp.json();
};

/**
 * Fetch import history.
 * @returns {Promise<{ imports: object[] }>}
 */
export const fetchImportHistory = async () => {
  const resp = await fetch('/api/imports');
  return resp.json();
};

/**
 * Toggle import enabled state.
 * @param {number} sequence
 * @returns {Promise<{ sequence: number, enabled: boolean }>}
 */
export const toggleImportEnabled = async (sequence) => {
  const resp = await fetch(`/api/imports/${sequence}/toggle`, {
    method: 'POST',
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Toggle failed');
  }
  return resp.json();
};

/**
 * Rebuild the database from vault log.
 * @returns {Promise<{ status: string, entries_processed: number, entries_by_type: object }>}
 */
export const rebuildDatabase = async () => {
  const resp = await fetch('/api/rebuild', {
    method: 'POST',
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Rebuild failed');
  }
  return resp.json();
};

/**
 * Import demo data by fetching demo files and uploading them through normal import.
 * @returns {Promise<{ results: object[] }>}
 */
export const importDemoData = async () => {
  // 1. Get list of demo files
  const listResp = await fetch('/api/demo-files');
  if (!listResp.ok) {
    throw new Error('Failed to fetch demo files list');
  }
  const { files } = await listResp.json();

  // 2. Download and upload each file
  const results = [];
  for (const fileInfo of files) {
    // Download the file
    const fileResp = await fetch(`/api/demo-files/${fileInfo.filename}`);
    if (!fileResp.ok) {
      throw new Error(`Failed to download ${fileInfo.filename}`);
    }
    const blob = await fileResp.blob();
    const file = new File([blob], fileInfo.filename);

    // Upload through normal import endpoint
    const result = await uploadCsv(file);
    results.push(result);
  }

  return { results };
};

/**
 * Upload a CSV file for import.
 * @param {File} file
 * @returns {Promise<object>}
 */
export const uploadCsv = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch('/api/import', {
    method: 'POST',
    body: formData,
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Import failed');
  }
  return resp.json();
};

/**
 * Upload a rules file.
 * @param {File} file
 * @returns {Promise<object>}
 */
export const uploadRules = async (file) => {
  const content = await file.text();
  const resp = await fetch('/api/rules', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  });
  if (!resp.ok) {
    const error = await resp.json();
    throw new Error(error.detail || 'Rules upload failed');
  }
  return resp.json();
};

/**
 * Fetch account value history.
 * @param {object} filters
 * @returns {Promise<object>}
 */
export const fetchAccountValueHistory = async (filters) => {
  const qs = buildQueryString(filters);
  const resp = await fetch(`/api/account_value_history?${qs}`);
  return resp.json();
};

/**
 * Create API functions bound to reactive state.
 * @param {object} options
 * @returns {object} API functions
 */
export const createApi = ({
  view,
  filters,
  tab,
  selectedCategory,
  searchQuery,
  pivotDepth,
  breakoutGranularity,
  summary,
  tree,
  pivot,
  cashflow,
  breakout,
  transactions,
  reportText,
  ensureCategoryColors,
  renderTreemap,
  renderSankey,
  renderBreakout,
  nextTick,
}) => {
  const requestIds = {
    summary: 0,
    tree: 0,
    pivot: 0,
    cashflow: 0,
    breakout: 0,
    report: 0,
    transactions: 0,
  };

  const beginRequest = (key) => {
    requestIds[key] += 1;
    return requestIds[key];
  };

  const isCurrentRequest = (key, requestId) => requestIds[key] === requestId;

  const loadSummary = async () => {
    const requestId = beginRequest('summary');
    const query = new URLSearchParams();
    if (selectedCategory.value) query.set('category', selectedCategory.value);
    if (searchQuery.value) query.set('q', searchQuery.value);
    const path = query.size ? `/api/summary?${query.toString()}` : '/api/summary';
    const data = await fetchJson(path, filters);
    if (!isCurrentRequest('summary', requestId)) return;
    summary.value = data;
  };

  const loadTree = async () => {
    const requestId = beginRequest('tree');
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    const qParam = searchQuery.value
      ? `&q=${encodeURIComponent(searchQuery.value)}`
      : '';
    const data = await fetchJson(`/api/tree?tab=${tab.value}${catParam}${qParam}`, filters);
    if (!isCurrentRequest('tree', requestId)) return;
    tree.value = data;
    if (data?.children) {
      ensureCategoryColors(data.children.map((l1) => l1.name));
    }
    await nextTick();
    if (!isCurrentRequest('tree', requestId)) return;
    renderTreemap();
  };

  const loadPivot = async () => {
    const requestId = beginRequest('pivot');
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    const qParam = searchQuery.value
      ? `&q=${encodeURIComponent(searchQuery.value)}`
      : '';
    const data = await fetchJson(
      `/api/pivot?tab=${tab.value}&depth=${pivotDepth.value}${catParam}${qParam}`,
      filters
    );
    if (!isCurrentRequest('pivot', requestId)) return;
    pivot.value = data;
  };

  const loadCashflow = async () => {
    const requestId = beginRequest('cashflow');
    const query = new URLSearchParams();
    if (selectedCategory.value) query.set('category', selectedCategory.value);
    if (searchQuery.value) query.set('q', searchQuery.value);
    const params = query.size ? `?${query.toString()}` : '';
    const data = await fetchJson(`/api/cashflow${params}`, filters);
    if (!isCurrentRequest('cashflow', requestId)) return;
    cashflow.value = data;
    await nextTick();
    if (!isCurrentRequest('cashflow', requestId)) return;
    renderSankey();
  };

  const loadBreakout = async () => {
    const requestId = beginRequest('breakout');
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    const qParam = searchQuery.value
      ? `&q=${encodeURIComponent(searchQuery.value)}`
      : '';
    const data = await fetchJson(
      `/api/breakout?granularity=${breakoutGranularity.value}${catParam}${qParam}`,
      filters
    );
    if (!isCurrentRequest('breakout', requestId)) return;
    breakout.value = data;
    ensureCategoryColors((data?.categories || []).map((cat) => cat.name));
    await nextTick();
    if (!isCurrentRequest('breakout', requestId)) return;
    renderBreakout();
  };

  const loadReport = async () => {
    const requestId = beginRequest('report');
    const qs = buildQueryString(filters);
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    const qParam = searchQuery.value
      ? `&q=${encodeURIComponent(searchQuery.value)}`
      : '';
    const resp = await fetch(`/api/report?${qs}${catParam}${qParam}`);
    const text = await resp.text();
    if (!isCurrentRequest('report', requestId)) return;
    reportText.value = text;
  };

  const loadTransactions = async () => {
    const requestId = beginRequest('transactions');
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    const tabParam =
      view.value === 'transactions' || tab.value === 'cashflow' || tab.value === 'breakout' || tab.value === 'report'
        ? ''
        : `&tab=${tab.value}`;
    const qParam = searchQuery.value
      ? `&q=${encodeURIComponent(searchQuery.value)}`
      : '';
    const data = await fetchJson(
      `/api/transactions?${tabParam}${catParam}${qParam}`,
      filters
    );
    if (!isCurrentRequest('transactions', requestId)) return;
    transactions.value = data;
  };

  const loadAll = async () => {
    if (!filters.from || !filters.to) return;
    const loads = [loadSummary()];
    if (tab.value === 'cashflow') {
      loads.push(loadCashflow());
    } else if (tab.value === 'breakout') {
      loads.push(loadBreakout());
    } else if (tab.value === 'report') {
      loads.push(loadReport());
    } else {
      loads.push(loadTree());
      loads.push(loadPivot());
    }
    await Promise.all(loads);
  };

  return {
    loadSummary,
    loadTree,
    loadPivot,
    loadCashflow,
    loadBreakout,
    loadReport,
    loadTransactions,
    loadAll,
  };
};
