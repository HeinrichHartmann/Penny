/**
 * Penny - Main Application Entry Point
 */
import { computed, createApp, nextTick, onMounted, reactive, ref, watch } from 'vue/dist/vue.esm-bundler.js';

import {
  createDateHelpers,
  computeDefaultDateRange,
} from './utils/date.js';
import { categoryColor, ensureCategoryColors } from './utils/color.js';
import {
  fetchMeta,
  fetchCategoryOptions,
  createApi,
  fetchAccountValueHistory,
} from './api.js';
import { initializeAppState } from './app/init.js';
import { setupAppLifecycle } from './app/lifecycle.js';
import { readUrlState, syncUrlState } from './app/urlState.js';
import {
  createBalanceViewModel,
  createReportViewModel,
  createTransactionsViewModel,
} from './app/viewModels.js';
import { createChartManager } from './charts.js';
import { SidebarNav } from './components/SidebarNav.js';
import { AccountsView } from './views/AccountsView.js';
import { BalanceView } from './views/BalanceView.js';
import { ImportView } from './views/ImportView.js';
import { ReportView } from './views/ReportView.js';
import { createReportViewState } from './views/report.js';
import { createBalanceViewState } from './views/balance.js';
import { RulesView } from './views/RulesView.js';
import { SettingsView } from './views/SettingsView.js';
import { createSelectorState } from './views/selector.js';
import { createTransactionsViewState } from './views/transactions.js';
import { TransactionsView } from './views/TransactionsView.js';

createApp({
  components: {
    SidebarNav,
    AccountsView,
    BalanceView,
    ImportView,
    ReportView,
    RulesView,
    SettingsView,
    TransactionsView,
  },
  setup() {
    const initialUrlState = readUrlState();
    let isHydratingFromUrl = true;

    // ── State ────────────────────────────────────────────────────────────────
    const view = ref('import');
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
    const setTreemapEl = (el) => {
      treemapEl.value = el;
    };
    const setSankeyEl = (el) => {
      sankeyEl.value = el;
    };
    const setBreakoutEl = (el) => {
      breakoutEl.value = el;
    };

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
      currentTransactionPage,
      resetTransactionPagination,
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
        return;
      }

      if (view.value === 'balance') {
        await balanceViewState.loadValueHistory();
      }
    };

    const refreshMeta = async () => {
      const m = await fetchMeta();
      meta.accounts = m.accounts;
      meta.min_date = m.min_date;
      meta.max_date = m.max_date;
    };

    const handleImportComplete = async (importResult) => {
      const oldMaxDate = meta.max_date;
      await refreshMeta();
      await loadCategoryOptions();

      // If a new account was created, add it to the filter
      // Handle both single result and array of results (multi-file import)
      const results = Array.isArray(importResult) ? importResult : [importResult];
      for (const result of results) {
        if (result?.account?.is_new && result?.account?.id) {
          const accountId = result.account.id;
          if (!filters.accounts.includes(accountId)) {
            filters.accounts.push(accountId);
          }
        }
      }

      // Update date range to show imported data
      if (meta.max_date) {
        if (!oldMaxDate) {
          // First import - reset filters to show last month of imported data
          const defaultRange = computeDefaultDateRange(meta.max_date);
          filters.from = defaultRange.from;
          filters.to = defaultRange.to;
        } else if (meta.max_date > oldMaxDate) {
          // Subsequent import - extend range to include new data
          if (filters.to && filters.to < meta.max_date) {
            filters.to = meta.max_date;
          }
        }
      }

      // Reload the current view to show the imported data
      await loadCurrentViewData({ resetTransactionsPage: true });
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

    const applyAccountFilter = (accountId) => {
      const id = typeof accountId === 'object' ? accountId.id : accountId;
      filters.accounts = id == null ? [] : [id];
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

    const transactionsViewModel = createTransactionsViewModel({
      selectorState,
      selectorActions,
      transactions,
      loadTransactions: loadTransactionsForCurrentView,
      currentTransactionPage,
      totalTransactionPages,
      transactionPageButtons,
      visibleTransactions,
      filteredTransactionCount,
      transactionRangeStart,
      transactionRangeEnd,
      searchQuery,
      categoryColor: getCategoryColor,
      applyAccountFilter,
      applyCategorySelection,
      toggleTransactionSort,
      transactionSortMarker,
      goToTransactionPage,
      goToPreviousTransactionPage,
      goToNextTransactionPage,
    });

    const reportViewModel = createReportViewModel({
      selectorState,
      selectorActions,
      summary,
      loadReportData: loadAll,
      tab,
      setTab: async (value) => {
        tab.value = value;
        if (view.value === 'report') {
          await loadAll();
        }
      },
      breakout,
      breakoutGranularity,
      breakoutGranularityMode,
      setBreakoutGranularityMode: (value) => {
        breakoutGranularityMode.value = value;
      },
      breakoutShowIncome,
      setBreakoutShowIncome: (value) => {
        breakoutShowIncome.value = value;
      },
      breakoutShowExpenses,
      setBreakoutShowExpenses: (value) => {
        breakoutShowExpenses.value = value;
      },
      breakoutNet,
      breakoutNetByPeriod,
      reportText,
      copyReport,
      copyLabel,
      pivot,
      pivotCopyLabel,
      copyPivotTable,
      pivotDepth,
      setPivotDepth: (value) => {
        pivotDepth.value = value;
      },
      applyCategorySelection,
      selectedMatchesCategory,
      categoryColor: getCategoryColor,
      setTreemapEl,
      setSankeyEl,
      setBreakoutEl,
    });

    const balanceViewState = createBalanceViewState({
      fetchAccountValueHistory,
      filters,
      onDateRangeChange: (from, to) => {
        filters.from = from;
        filters.to = to;
      },
    });

    const balanceViewModel = createBalanceViewModel({
      selectorState,
      selectorActions,
      ...balanceViewState,
    });

    const syncUrl = () => {
      if (isHydratingFromUrl) return;
      syncUrlState({
        view: view.value,
        tab: tab.value,
        filters,
        selectedCategory: selectedCategory.value,
        searchQuery: searchQuery.value,
        pivotDepth: pivotDepth.value,
        breakoutGranularityMode: breakoutGranularityMode.value,
        breakoutShowIncome: breakoutShowIncome.value,
        breakoutShowExpenses: breakoutShowExpenses.value,
        currentTransactionPage: currentTransactionPage.value,
      });
    };

    setupAppLifecycle({
      watch,
      onMounted,
      isHydrating: () => isHydratingFromUrl,
      setHydrating: (value) => {
        isHydratingFromUrl = value;
      },
      initialUrlState,
      initializeAppState,
      fetchMeta,
      meta,
      filters,
      yearButtons,
      loadCategoryOptions,
      loadCurrentViewData,
      loadAll,
      renderBreakout,
      loadPivot,
      loadBreakout,
      syncUrl,
      view,
      tab,
      selectedCategory,
      searchQuery,
      pivotDepth,
      breakoutGranularityMode,
      breakoutShowIncome,
      breakoutShowExpenses,
      currentTransactionPage,
    });

    // ── Expose ───────────────────────────────────────────────────────────────
    return {
      view,
      filters,
      transactionsViewModel,
      reportViewModel,
      balanceViewModel,
      toggleAccount,
      handleImportComplete,
      refreshMeta,
    };
  },
}).mount('#app');
