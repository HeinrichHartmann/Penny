/**
 * Penny - Main Application Entry Point
 */
import { computed, createApp, nextTick, onMounted, reactive, ref, watch } from 'vue/dist/vue.esm-bundler.js';

import { formatCurrency, formatCompactSigned } from './utils/format.js';
import {
  MONTH_BUTTONS,
  createDateHelpers,
  breakoutGranularityLabel,
  computeYearButtons,
  computeDefaultDateRange,
} from './utils/date.js';
import { categoryColor, ensureCategoryColors } from './utils/color.js';
import {
  fetchMeta,
  fetchAccounts,
  fetchCategoryOptions,
  uploadCsv,
  updateAccount,
  createApi,
} from './api.js';
import { createChartManager } from './charts.js';
import { SelectorHeader } from './components/SelectorHeader.js';
import { createAccountsViewState } from './views/accounts.js';
import { createImportViewState } from './views/import.js';
import { ImportView } from './views/ImportView.js';
import { createReportViewState } from './views/report.js';
import { RulesView } from './views/RulesView.js';
import { createSelectorState } from './views/selector.js';
import { createTransactionsViewState } from './views/transactions.js';

createApp({
  components: {
    ImportView,
    SelectorHeader,
    RulesView,
  },
  setup() {
    const readUrlState = () => {
      const params = new URLSearchParams(window.location.search);
      return {
        view: params.get('view'),
        tab: params.get('tab'),
        from: params.get('from'),
        to: params.get('to'),
        accounts: params.get('accounts')?.split(',').filter(Boolean) || null,
        neutralize: params.get('neutralize'),
        category: params.get('category'),
        q: params.get('q'),
        pivotDepth: params.get('pivotDepth'),
        breakoutGranularityMode: params.get('breakoutGranularityMode'),
        breakoutShowIncome: params.get('breakoutShowIncome'),
        breakoutShowExpenses: params.get('breakoutShowExpenses'),
        transactionPage: params.get('transactionPage'),
      };
    };

    const initialUrlState = readUrlState();
    let isHydratingFromUrl = true;

    // ── State ────────────────────────────────────────────────────────────────
    const view = ref(initialUrlState.view || 'report');
    const meta = reactive({ accounts: [], min_date: '', max_date: '' });
    const filters = reactive({
      from: '',
      to: '',
      accounts: [],
      neutralize: true,
    });
    const tab = ref(initialUrlState.tab || 'expense');
    const summary = ref(null);
    const tree = ref(null);
    const pivot = ref(null);
    const cashflow = ref(null);
    const breakout = ref(null);
    const breakoutGranularityMode = ref(initialUrlState.breakoutGranularityMode || 'auto');
    const breakoutShowIncome = ref(initialUrlState.breakoutShowIncome !== 'false');
    const breakoutShowExpenses = ref(initialUrlState.breakoutShowExpenses !== 'false');
    const pivotDepth = ref(initialUrlState.pivotDepth || '1');
    const transactions = ref(null);
    const selectedCategory = ref(initialUrlState.category || null);
    const yearButtons = ref([]);
    const categoryColorMap = reactive({});
    const reportText = ref('');
    const searchQuery = ref(initialUrlState.q || '');
    const monthRangeAnchor = ref(null);

    // Chart element refs
    const treemapEl = ref(null);
    const sankeyEl = ref(null);
    const breakoutEl = ref(null);

    // ── Date Helpers ─────────────────────────────────────────────────────────
    const dateHelpers = createDateHelpers(filters, meta, monthRangeAnchor);
    const {
      setYear,
      setAll,
      setMonth,
      setYearAllMonths,
      isActiveMonth,
      isActiveYear,
      getMonthShortcutYear,
      computeBreakoutGranularity,
    } = dateHelpers;

    const monthShortcutYear = computed(() => getMonthShortcutYear());

    const breakoutGranularity = computed(() =>
      computeBreakoutGranularity(breakoutGranularityMode.value)
    );

    // ── Color Helper ─────────────────────────────────────────────────────────
    const getCategoryColor = (cat) => categoryColor(cat, categoryColorMap);

    const updateCategoryColors = (categories) => {
      ensureCategoryColors(categories, categoryColorMap);
    };

    // ── Chart Manager ────────────────────────────────────────────────────────
    const chartManager = createChartManager({
      treemapEl,
      sankeyEl,
      breakoutEl,
      tree,
      cashflow,
      breakout,
      breakoutShowIncome,
      breakoutShowExpenses,
      categoryColorFn: getCategoryColor,
      onCategorySelect: (category) => applyCategorySelection(category),
    });

    const { renderTreemap, renderSankey, renderBreakout } = chartManager;

    // ── API ──────────────────────────────────────────────────────────────────
    const api = createApi({
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
      ensureCategoryColors: updateCategoryColors,
      renderTreemap,
      renderSankey,
      renderBreakout,
      nextTick,
    });

    const {
      loadSummary,
      loadTree,
      loadPivot,
      loadCashflow,
      loadBreakout,
      loadReport,
      loadTransactions,
      loadAll,
    } = api;

    const transactionsView = createTransactionsViewState({
      transactions,
      initialPage: initialUrlState.transactionPage,
    });

    const {
      transactionsCopyLabel,
      currentTransactionPage,
      transactionSort,
      resetTransactionPagination,
      sortedTransactions,
      totalTransactionPages,
      visibleTransactions,
      filteredTransactionCount,
      transactionRangeStart,
      transactionRangeEnd,
      transactionPageButtons,
      toggleTransactionSort,
      transactionSortMarker,
      goToTransactionPage,
      goToPreviousTransactionPage,
      goToNextTransactionPage,
      copyTransactionsTable,
    } = transactionsView;

    const loadTransactionsForCurrentView = async ({ resetPage = false } = {}) => {
      if (resetPage) {
        resetTransactionPagination();
      }
      await loadTransactions();
    };

    const loadCurrentViewData = async ({ resetTransactionsPage = false } = {}) => {
      if (isHydratingFromUrl) return;

      if (view.value === 'transactions') {
        await loadTransactionsForCurrentView({ resetPage: resetTransactionsPage });
        return;
      }

      if (view.value === 'report') {
        await loadAll();
      }
    };

    const refreshMeta = async () => {
      const m = await fetchMeta();
      meta.accounts = m.accounts;
      meta.min_date = m.min_date;
      meta.max_date = m.max_date;
    };

    const accountsView = createAccountsViewState({
      fetchAccounts,
      updateAccount,
      refreshMeta,
    });

    const {
      accountsList,
      accountsLoading,
      editingAccountId,
      editingAccountName,
      loadAccounts,
      startEditingAccount,
      cancelEditingAccount,
      saveAccountName,
    } = accountsView;

    const handleImportComplete = async () => {
      await Promise.all([loadAccounts(), refreshMeta()]);
      await loadCategoryOptions();
    };

    // ── Account Toggle ───────────────────────────────────────────────────────
    const toggleAccount = (accountId) => {
      // accountId can be either an integer ID or an object with id property
      const id = typeof accountId === 'object' ? accountId.id : accountId;
      const index = filters.accounts.indexOf(id);
      if (index === -1) {
        filters.accounts.push(id);
      } else {
        filters.accounts.splice(index, 1);
      }
    };

    const selectorView = createSelectorState({
      filters,
      meta,
      yearButtons,
      monthShortcutYear,
      selectedCategory,
      searchQuery,
      toggleAccount,
      setYear,
      setAll,
      setMonth,
      setYearAllMonths,
      isActiveYear,
      isActiveMonth,
      view,
      loadTransactionsForCurrentView,
      loadAll,
      fetchCategoryOptions,
    });

    const {
      selectorCategory,
      categorySelectValue,
      selectedMatchesCategory,
      categoryBreadcrumbs,
      nextCategoryOptions,
      loadCategoryOptions,
      applyCategorySelection,
      clearSelection,
      previewCategorySelection,
      selectorState,
      selectorActions,
    } = selectorView;

    const reportView = createReportViewState({
      breakout,
      pivot,
      reportText,
    });

    const {
      copyLabel,
      pivotCopyLabel,
      breakoutNet,
      breakoutNetByPeriod,
      copyReport,
      copyPivotTable,
    } = reportView;

    // ── Watchers ─────────────────────────────────────────────────────────────
    watch(
      () => [filters.from, filters.to, filters.accounts.join(','), filters.neutralize],
      () => {
        loadCategoryOptions();
        loadCurrentViewData({ resetTransactionsPage: true });
      }
    );

    watch(tab, () => {
      if (isHydratingFromUrl || view.value !== 'report') return;
      loadAll();
    });

    watch(view, async () => {
      if (view.value === 'accounts') {
        await loadAccounts();
      } else {
        loadCurrentViewData();
      }
    });

    watch(searchQuery, () => {
      if (isHydratingFromUrl) return;
      loadCategoryOptions();
      loadCurrentViewData({ resetTransactionsPage: true });
    });

    const syncUrlState = () => {
      if (isHydratingFromUrl) return;

      const params = new URLSearchParams();
      params.set('view', view.value);
      params.set('tab', tab.value);

      if (filters.from) params.set('from', filters.from);
      if (filters.to) params.set('to', filters.to);
      params.set('accounts', filters.accounts.join(','));
      params.set('neutralize', String(filters.neutralize));

      if (selectedCategory.value) params.set('category', selectedCategory.value);
      if (searchQuery.value) params.set('q', searchQuery.value);

      params.set('pivotDepth', pivotDepth.value);
      params.set('breakoutGranularityMode', breakoutGranularityMode.value);
      params.set('breakoutShowIncome', String(breakoutShowIncome.value));
      params.set('breakoutShowExpenses', String(breakoutShowExpenses.value));
      params.set('transactionPage', String(currentTransactionPage.value));

      const query = params.toString();
      const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
      window.history.replaceState(null, '', nextUrl);
    };

    watch(
      () => [
        view.value,
        tab.value,
        filters.from,
        filters.to,
        filters.accounts.join(','),
        filters.neutralize,
        selectedCategory.value,
        searchQuery.value,
        pivotDepth.value,
        breakoutGranularityMode.value,
        breakoutShowIncome.value,
        breakoutShowExpenses.value,
        currentTransactionPage.value,
      ],
      syncUrlState
    );

    watch(pivotDepth, () => {
      if (isHydratingFromUrl || view.value !== 'report') return;
      if (tab.value === 'expense' || tab.value === 'income') loadPivot();
    });

    watch(breakoutGranularityMode, () => {
      if (isHydratingFromUrl || view.value !== 'report') return;
      if (tab.value === 'breakout') loadBreakout();
    });

    watch([breakoutShowIncome, breakoutShowExpenses], () => {
      if (isHydratingFromUrl || view.value !== 'report') return;
      if (tab.value === 'breakout') renderBreakout();
    });

    // ── Init ─────────────────────────────────────────────────────────────────
    onMounted(async () => {
      const m = await fetchMeta();
      meta.accounts = m.accounts;  // Now array of account objects with id, label, etc.
      meta.min_date = m.min_date;
      meta.max_date = m.max_date;

      yearButtons.value = computeYearButtons(m.min_date, m.max_date);

      const defaultRange = computeDefaultDateRange(m.max_date);
      filters.from = initialUrlState.from || defaultRange.from;
      filters.to = initialUrlState.to || defaultRange.to;

      // Extract account IDs (meta.accounts now contains objects)
      const allAccountIds = m.accounts.map((acc) => acc.id);
      filters.accounts = initialUrlState.accounts
        ? initialUrlState.accounts.map(Number).filter((id) => allAccountIds.includes(id))
        : [...allAccountIds];
      filters.neutralize = initialUrlState.neutralize == null
        ? true
        : initialUrlState.neutralize !== 'false';

      isHydratingFromUrl = false;
      await loadCategoryOptions();
      syncUrlState();
      await loadCurrentViewData();
    });

    // ── Expose ───────────────────────────────────────────────────────────────
    return {
      // State
      view,
      meta,
      filters,
      tab,
      summary,
      tree,
      pivot,
      cashflow,
      breakout,
      transactions,
      selectedCategory,
      selectorCategory,
      yearButtons,
      reportText,
      copyLabel,
      pivotCopyLabel,
      transactionsCopyLabel,
      searchQuery,
      categorySelectValue,
      nextCategoryOptions,
      selectorState,
      selectorActions,
      currentTransactionPage,
      transactionSort,
      pivotDepth,
      breakoutGranularityMode,
      breakoutGranularity,
      breakoutShowIncome,
      breakoutShowExpenses,

      // Chart refs
      treemapEl,
      sankeyEl,
      breakoutEl,

      // Formatting
      formatCurrency,
      formatCompactSigned,
      breakoutGranularityLabel,

      // Date helpers
      monthButtons: MONTH_BUTTONS,
      monthShortcutYear,
      setYear,
      setAll,
      setMonth,
      setYearAllMonths,
      isActiveYear,
      isActiveMonth,

      // Account
      toggleAccount,

      // Category
      categoryColor: getCategoryColor,
      selectedMatchesCategory,
      categoryBreadcrumbs,
      applyCategorySelection,
      clearSelection,
      previewCategorySelection,

      // Breakout
      breakoutNet,
      breakoutNetByPeriod,

      // Transactions
      sortedTransactions,
      totalTransactionPages,
      transactionRangeStart,
      transactionRangeEnd,
      transactionPageButtons,
      visibleTransactions,
      filteredTransactionCount,
      toggleTransactionSort,
      transactionSortMarker,
      goToTransactionPage,
      goToPreviousTransactionPage,
      goToNextTransactionPage,

      // Copy
      copyReport,
      copyPivotTable,
      copyTransactionsTable,
      handleImportComplete,

      // Accounts
      accountsList,
      accountsLoading,
      loadAccounts,
      editingAccountId,
      editingAccountName,
      startEditingAccount,
      cancelEditingAccount,
      saveAccountName,
    };
  },
}).mount('#app');
