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
 * @returns {Promise<{ accounts: string[], min_date: string, max_date: string }>}
 */
export const fetchMeta = async () => {
  const resp = await fetch('/api/meta');
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
    const data = await fetchJson('/api/summary', filters);
    if (!isCurrentRequest('summary', requestId)) return;
    summary.value = data;
  };

  const loadTree = async () => {
    const requestId = beginRequest('tree');
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    const data = await fetchJson(`/api/tree?tab=${tab.value}${catParam}`, filters);
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
    const data = await fetchJson(
      `/api/pivot?tab=${tab.value}&depth=${pivotDepth.value}${catParam}`,
      filters
    );
    if (!isCurrentRequest('pivot', requestId)) return;
    pivot.value = data;
  };

  const loadCashflow = async () => {
    const requestId = beginRequest('cashflow');
    const params = selectedCategory.value
      ? `?category=${encodeURIComponent(selectedCategory.value)}`
      : '';
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
    const data = await fetchJson(
      `/api/breakout?granularity=${breakoutGranularity.value}${catParam}`,
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
    const resp = await fetch(`/api/report?${qs}`);
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
