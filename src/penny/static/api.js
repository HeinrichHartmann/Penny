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
  resetTransactionWindow,
  nextTick,
}) => {
  const loadSummary = async () => {
    summary.value = await fetchJson('/api/summary', filters);
  };

  const loadTree = async () => {
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    tree.value = await fetchJson(`/api/tree?tab=${tab.value}${catParam}`, filters);
    if (tree.value?.children) {
      ensureCategoryColors(tree.value.children.map((l1) => l1.name));
    }
    await nextTick();
    renderTreemap();
  };

  const loadPivot = async () => {
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    pivot.value = await fetchJson(
      `/api/pivot?tab=${tab.value}&depth=${pivotDepth.value}${catParam}`,
      filters
    );
  };

  const loadCashflow = async () => {
    const params = selectedCategory.value
      ? `?category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    cashflow.value = await fetchJson(`/api/cashflow${params}`, filters);
    await nextTick();
    renderSankey();
  };

  const loadBreakout = async () => {
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    breakout.value = await fetchJson(
      `/api/breakout?granularity=${breakoutGranularity.value}${catParam}`,
      filters
    );
    ensureCategoryColors((breakout.value?.categories || []).map((cat) => cat.name));
    await nextTick();
    renderBreakout();
  };

  const loadReport = async () => {
    const qs = buildQueryString(filters);
    const resp = await fetch(`/api/report?${qs}`);
    reportText.value = await resp.text();
  };

  const loadTransactions = async () => {
    const catParam = selectedCategory.value
      ? `&category=${encodeURIComponent(selectedCategory.value)}`
      : '';
    const tabParam =
      tab.value === 'cashflow' || tab.value === 'breakout' ? '' : `&tab=${tab.value}`;
    const qParam = searchQuery.value
      ? `&q=${encodeURIComponent(searchQuery.value)}`
      : '';
    transactions.value = await fetchJson(
      `/api/transactions?${tabParam}${catParam}${qParam}`,
      filters
    );
    resetTransactionWindow();
  };

  const loadAll = async () => {
    if (!filters.from || !filters.to) return;
    const loads = [loadSummary()];
    if (tab.value === 'cashflow') {
      loads.push(loadCashflow());
      loads.push(loadTransactions());
    } else if (tab.value === 'breakout') {
      loads.push(loadBreakout());
      loads.push(loadTransactions());
    } else if (tab.value === 'report') {
      loads.push(loadReport());
    } else {
      loads.push(loadTree());
      loads.push(loadPivot());
      loads.push(loadTransactions());
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
