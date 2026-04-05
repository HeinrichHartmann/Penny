/**
 * Penny - Main Application Entry Point
 */
import { computed, createApp, nextTick, onMounted, reactive, ref, watch } from 'vue/dist/vue.esm-bundler.js';

import {
  createDateHelpers,
  computeDefaultDateRange,
  computeYearButtons,
} from './utils/date.js';
import { categoryColor, ensureCategoryColors } from './utils/color.js';
import {
  deleteAccount,
  fetchAccounts,
  fetchAccountValueHistory,
  fetchCategoryOptions,
  fetchMeta,
  fetchImportHistory,
  fetchRules,
  importDemoData,
  rebuildDatabase,
  recordBalanceSnapshot,
  runRules,
  saveRules,
  toggleImportEnabled,
  updateAccount,
  uploadCsv,
  uploadRules,
  createApi,
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

const emptyRulesState = () => ({
  path: '',
  directory: '',
  exists: false,
  content: '',
  originalContent: '',
  loading: false,
  saving: false,
  running: false,
  error: null,
  saveMessage: null,
  lastRunAt: null,
  logs: [],
  stats: null,
});

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
    const view = ref(initialUrlState.view || 'import');
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
    const balanceValueHistory = ref(null);
    const balanceLoading = ref(false);
    const selectedCategory = ref(initialUrlState.category || null);
    const yearButtons = ref([]);
    const categoryOptions = ref([]);
    const categoryColorMap = reactive({});
    const reportText = ref('');
    const searchQuery = ref(initialUrlState.q || '');
    const monthRangeAnchor = ref(null);
    const appDataVersion = ref(0);

    // ADR-013: app.js owns all server-backed frontend state. Views render props only.
    const importModel = reactive({
      isUploading: false,
      lastResult: null,
      error: null,
      history: [],
      historyLoading: false,
      rebuilding: false,
      rebuildResult: null,
      importingDemo: false,
    });

    const accountsModel = reactive({
      accounts: [],
      loading: false,
      includeHidden: false,
    });

    const rulesModel = reactive(emptyRulesState());

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

    const safeLoad = async (label, loader) => {
      try {
        await loader();
      } catch (error) {
        console.error(`Failed to load ${label}:`, error);
      }
    };

    const loadCurrentViewData = async ({ resetTransactionsPage = false } = {}) => {
      if (isHydratingFromUrl) return;
      await Promise.all([
        safeLoad('transactions', () =>
          loadTransactionsForCurrentView({ resetPage: resetTransactionsPage })
        ),
        safeLoad('report', loadAll),
        safeLoad('balance', loadBalanceValueHistory),
      ]);
    };

    const refreshMeta = async () => {
      const m = await fetchMeta();
      meta.accounts = m.accounts;
      meta.min_date = m.min_date;
      meta.max_date = m.max_date;
      yearButtons.value = m.min_date && m.max_date
        ? computeYearButtons(m.min_date, m.max_date)
        : [];
      return m;
    };

    const applyRulesPayload = (data, { preserveDraft = false } = {}) => {
      const nextContent = data.content || '';
      const previousHasChanges = rulesModel.content !== rulesModel.originalContent;

      rulesModel.path = data.path;
      rulesModel.directory = data.directory;
      rulesModel.exists = data.exists;
      rulesModel.originalContent = nextContent;
      rulesModel.lastRunAt = data.latest_run?.started_at || null;
      rulesModel.logs = data.latest_run?.logs || [];
      rulesModel.stats = data.latest_run?.stats || null;
      rulesModel.error = data.latest_run?.status === 'error'
        ? 'Classification failed - see logs below'
        : null;

      if (!preserveDraft || !previousHasChanges) {
        rulesModel.content = nextContent;
      }
    };

    const loadImportHistory = async () => {
      importModel.historyLoading = true;
      try {
        const data = await fetchImportHistory();
        importModel.history = data.imports || [];
      } catch (error) {
        console.error('Failed to load import history:', error);
        importModel.history = [];
      } finally {
        importModel.historyLoading = false;
      }
    };

    const loadAccounts = async () => {
      accountsModel.loading = true;
      try {
        const data = await fetchAccounts(accountsModel.includeHidden);
        accountsModel.accounts = data.accounts || [];
      } finally {
        accountsModel.loading = false;
      }
    };

    const loadRules = async ({ preserveDraft = false } = {}) => {
      rulesModel.loading = true;
      rulesModel.error = null;
      try {
        const data = await fetchRules();
        applyRulesPayload(data, { preserveDraft });
      } catch (error) {
        rulesModel.error = error.message;
      } finally {
        rulesModel.loading = false;
      }
    };

    const loadCategoryOptions = async () => {
      const result = await fetchCategoryOptions(filters, searchQuery.value);
      categoryOptions.value = result.categories || [];
    };

    const loadSharedServerState = async ({ preserveRulesDraft = false } = {}) => {
      await Promise.all([
        loadImportHistory(),
        loadAccounts(),
        loadRules({ preserveDraft: preserveRulesDraft }),
      ]);
    };

    let balanceViewState = null;

    const loadBalanceValueHistory = async () => {
      if (!filters.accounts || filters.accounts.length === 0) {
        balanceValueHistory.value = null;
        return;
      }

      balanceLoading.value = true;
      try {
        const data = await fetchAccountValueHistory(filters);
        balanceValueHistory.value = data;
        await nextTick();
        balanceViewState?.renderBalanceChart();
      } catch (error) {
        console.error('Failed to load value history:', error);
        balanceValueHistory.value = null;
      } finally {
        balanceLoading.value = false;
      }
    };

    const clearDerivedViewData = () => {
      summary.value = null;
      tree.value = null;
      pivot.value = null;
      cashflow.value = null;
      breakout.value = null;
      transactions.value = null;
      reportText.value = '';
      balanceViewState?.resetValueHistory();
      resetTransactionPagination();
    };

    let pendingRehydration = Promise.resolve();
    const rehydrateAppState = ({
      updateDateRange = false,
      preserveRulesDraft = false,
    } = {}) => {
      pendingRehydration = pendingRehydration.then(async () => {
        isHydratingFromUrl = true;
        try {
          const oldMaxDate = meta.max_date;
          await refreshMeta();

          if (updateDateRange && meta.max_date) {
            if (!oldMaxDate) {
              const defaultRange = computeDefaultDateRange(meta.max_date);
              filters.from = defaultRange.from;
              filters.to = defaultRange.to;
            } else if (meta.max_date > oldMaxDate && filters.to && filters.to < meta.max_date) {
              filters.to = meta.max_date;
            }
          }

          const visibleAccountIds = meta.accounts.map((account) => account.id);
          const selectedVisibleAccountIds = filters.accounts.filter((id) =>
            visibleAccountIds.includes(id)
          );
          filters.accounts = selectedVisibleAccountIds.length > 0
            ? selectedVisibleAccountIds
            : [...visibleAccountIds];

          clearDerivedViewData();

          // ADR-013: batch selector/meta updates so watchers do not reload against
          // half-updated query context during a full app rehydrate.
          await nextTick();

          await Promise.all([
            loadSharedServerState({ preserveRulesDraft }),
            loadCategoryOptions(),
          ]);
        } finally {
          isHydratingFromUrl = false;
        }

        syncUrl();
        await loadCurrentViewData({ resetTransactionsPage: true });
        appDataVersion.value += 1;
      });

      return pendingRehydration;
    };

    let pendingImportRefresh = Promise.resolve();
    const handleImportComplete = () => {
      pendingImportRefresh = pendingImportRefresh.then(async () => {
        await rehydrateAppState({ updateDateRange: true });
      });
      return pendingImportRefresh;
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
      categoryOptions,
      searchQuery,
      toggleAccount,
      setYear,
      setAll,
      setMonth,
      setYearAllMonths,
      isActiveYear,
      isActiveMonth,
    });

    const {
      selectedMatchesCategory,
      applyCategorySelection,
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

    balanceViewState = createBalanceViewState({
      valueHistory: balanceValueHistory,
      loading: balanceLoading,
      loadValueHistory: loadBalanceValueHistory,
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

    const rulesHasChanges = computed(() => rulesModel.content !== rulesModel.originalContent);
    const rulesViewModel = computed(() => ({
      ...rulesModel,
      hasChanges: rulesHasChanges.value,
    }));

    const uploadSelectedFiles = async (files) => {
      importModel.isUploading = true;
      importModel.error = null;
      importModel.lastResult = null;

      try {
        const results = [];
        for (const file of files) {
          if (file.name.endsWith('rules.py')) {
            const result = await uploadRules(file);
            results.push({
              filename: file.name,
              parser: 'rules',
              status: result.status,
              path: result.path,
              type: 'rules',
            });
          } else {
            results.push(await uploadCsv(file));
          }
        }

        importModel.lastResult = results[results.length - 1] || null;
        await handleImportComplete();
      } catch (error) {
        importModel.error = error.message;
      } finally {
        importModel.isUploading = false;
      }
    };

    const toggleImportEntryEnabled = async (sequence) => {
      await toggleImportEnabled(sequence);
      await rehydrateAppState({ preserveRulesDraft: true });
    };

    const rebuildProjection = async () => {
      importModel.rebuilding = true;
      importModel.rebuildResult = null;
      try {
        importModel.rebuildResult = await rebuildDatabase();
        await rehydrateAppState({ preserveRulesDraft: true });
      } finally {
        importModel.rebuilding = false;
      }
    };

    const importDemo = async () => {
      importModel.importingDemo = true;
      importModel.error = null;
      try {
        const { results } = await importDemoData();
        importModel.lastResult = results[results.length - 1] || null;
        await handleImportComplete();
      } catch (error) {
        importModel.error = error.message;
      } finally {
        importModel.importingDemo = false;
      }
    };

    const setIncludeHiddenAccounts = async (value) => {
      accountsModel.includeHidden = value;
      await loadAccounts();
    };

    const saveAccountMetadata = async (accountId, updates) => {
      await updateAccount(accountId, updates);
      await rehydrateAppState({ preserveRulesDraft: true });
    };

    const saveBalanceSnapshot = async (accountId, snapshot) => {
      await recordBalanceSnapshot(accountId, snapshot);
      await rehydrateAppState({ preserveRulesDraft: true });
    };

    const archiveAccount = async (accountId) => {
      await deleteAccount(accountId);
      await rehydrateAppState({ preserveRulesDraft: true });
    };

    const updateRulesDraft = (value) => {
      rulesModel.content = value;
      rulesModel.saveMessage = null;
    };

    const reloadRulesView = async () => {
      await loadRules({ preserveDraft: true });
    };

    const runClassification = async () => {
      rulesModel.running = true;
      rulesModel.logs = [];
      rulesModel.stats = null;
      rulesModel.error = null;
      try {
        const result = await runRules();
        rulesModel.lastRunAt = result.started_at || null;
        rulesModel.logs = result.logs || [];
        rulesModel.stats = result.stats || null;
        rulesModel.error = result.status === 'error'
          ? 'Classification failed - see logs below'
          : null;
        await rehydrateAppState({ preserveRulesDraft: true });
      } catch (error) {
        rulesModel.error = error.message;
        rulesModel.logs = [{ level: 'error', message: error.message }];
      } finally {
        rulesModel.running = false;
      }
    };

    const saveRulesContent = async () => {
      rulesModel.saving = true;
      rulesModel.error = null;
      rulesModel.saveMessage = null;
      try {
        await saveRules(rulesModel.content);
        rulesModel.originalContent = rulesModel.content;
        rulesModel.saveMessage = 'Saved successfully';
        await runClassification();
      } catch (error) {
        rulesModel.error = error.message;
      } finally {
        rulesModel.saving = false;
      }
    };

    const importViewActions = {
      uploadSelectedFiles,
      toggleImportEntryEnabled,
      rebuildProjection,
      importDemo,
    };

    const accountsViewActions = {
      setIncludeHiddenAccounts,
      saveAccountMetadata,
      saveBalanceSnapshot,
      archiveAccount,
    };

    const rulesViewActions = {
      updateRulesDraft,
      reloadRulesView,
      runClassification,
      saveRulesContent,
    };

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
      refreshMeta,
      meta,
      filters,
      yearButtons,
      loadSharedServerState,
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
      appDataVersion,
      view,
      filters,
      importModel,
      importViewActions,
      accountsModel,
      accountsViewActions,
      rulesModel: rulesViewModel,
      rulesViewActions,
      rulesHasChanges,
      transactionsViewModel,
      reportViewModel,
      balanceViewModel,
      toggleAccount,
      refreshMeta,
      rehydrateAppState,
    };
  },
}).mount('#app');
