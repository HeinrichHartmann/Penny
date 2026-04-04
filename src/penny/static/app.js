/**
 * Penny - Main Application Entry Point
 */
import { computed, createApp, nextTick, onMounted, reactive, ref, watch } from 'vue/dist/vue.esm-bundler.js';

import { formatCurrency, formatCompactSigned, toMarkdownTable } from './utils/format.js';
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
  fetchRules,
  saveRules,
  runRules,
  createApi,
} from './api.js';
import { createChartManager } from './charts.js';
import { SelectorHeader } from './components/SelectorHeader.js';

createApp({
  components: {
    SelectorHeader,
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
    const copyLabel = ref('Copy to clipboard');
    const pivotCopyLabel = ref('MD');
    const transactionsCopyLabel = ref('MD');
    const searchQuery = ref(initialUrlState.q || '');
    const categorySelectValue = ref('');
    const availableCategories = ref([]);
    const currentTransactionPage = ref(Math.max(1, parseInt(initialUrlState.transactionPage || '1', 10) || 1));
    const transactionSort = reactive({ key: 'booking_date', direction: 'desc' });
    const monthRangeAnchor = ref(null);
    const TRANSACTIONS_PER_PAGE = 100;

    // Import state
    const importState = reactive({
      isDragging: false,
      isUploading: false,
      lastResult: null,
      error: null,
    });

    // Accounts state
    const accountsList = ref([]);
    const accountsLoading = ref(false);
    const editingAccountId = ref(null);
    const editingAccountName = ref('');

    // Rules state
    const rulesState = reactive({
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
      logs: [],
      stats: null,
    });

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

    // ── Transaction Pagination ───────────────────────────────────────────────
    const resetTransactionPagination = () => {
      currentTransactionPage.value = 1;
    };

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

    // ── Category Selection ───────────────────────────────────────────────────
    const selectedMatchesCategory = (category) => {
      if (!selectedCategory.value || !category) return false;
      return (
        selectedCategory.value === category ||
        selectedCategory.value.startsWith(`${category}/`)
      );
    };

    const categoryBreadcrumbs = computed(() => {
      if (!selectedCategory.value) return [];
      const parts = selectedCategory.value.split('/').filter(Boolean);
      return parts.map((label, index) => ({
        label,
        path: parts.slice(0, index + 1).join('/'),
      }));
    });

    const nextCategoryOptions = computed(() => {
      const options = new Map();
      const prefix = selectedCategory.value ? `${selectedCategory.value}/` : '';

      for (const category of availableCategories.value) {
        if (!category) continue;
        if (selectedCategory.value && !category.startsWith(prefix)) continue;

        const remainder = selectedCategory.value ? category.slice(prefix.length) : category;
        if (!remainder) continue;

        const nextSegment = remainder.split('/')[0];
        if (!nextSegment) continue;

        const path = selectedCategory.value
          ? `${selectedCategory.value}/${nextSegment}`
          : nextSegment;

        if (!options.has(path)) {
          options.set(path, { path, label: nextSegment });
        }
      }

      return Array.from(options.values()).sort((left, right) =>
        left.label.localeCompare(right.label, undefined, {
          sensitivity: 'base',
          numeric: true,
        })
      );
    });

    const applyCategorySelection = async (category) => {
      selectedCategory.value = category;

      if (view.value === 'transactions') {
        await loadTransactionsForCurrentView({ resetPage: true });
        return;
      }

      if (view.value === 'report') {
        await loadAll();
      }
    };

    const clearSelection = () => {
      applyCategorySelection(null);
    };

    // ── Breakout Computed ────────────────────────────────────────────────────
    const breakoutNet = computed(() => {
      if (!breakout.value) return null;
      return (breakout.value.income_total || 0) - (breakout.value.expense_total || 0);
    });

    const breakoutNetByPeriod = computed(() => {
      if (!breakout.value) return [];
      const count = breakout.value.periods?.length || 0;
      const sums = Array.from({ length: count }, () => 0);
      for (const cat of breakout.value.categories || []) {
        cat.values.forEach((value, index) => {
          sums[index] += value;
        });
      }
      return sums;
    });

    // ── Transaction Sorting ──────────────────────────────────────────────────
    const compareValues = (a, b) => {
      if (a == null && b == null) return 0;
      if (a == null) return 1;
      if (b == null) return -1;
      if (typeof a === 'number' && typeof b === 'number') return a - b;
      return String(a).localeCompare(String(b), undefined, {
        numeric: true,
        sensitivity: 'base',
      });
    };

    const filteredTransactions = computed(() => {
      return transactions.value?.transactions || [];
    });

    const sortedTransactions = computed(() => {
      const rows = [...filteredTransactions.value];
      const { key, direction } = transactionSort;
      const factor = direction === 'asc' ? 1 : -1;
      rows.sort((left, right) => {
        const primary = compareValues(left[key], right[key]) * factor;
        if (primary !== 0) return primary;
        return compareValues(left.fp, right.fp);
      });
      return rows;
    });

    const totalTransactionPages = computed(() => {
      const rows = sortedTransactions.value;
      return Math.max(1, Math.ceil(rows.length / TRANSACTIONS_PER_PAGE));
    });

    const visibleTransactions = computed(() => {
      const rows = sortedTransactions.value;
      const start = (currentTransactionPage.value - 1) * TRANSACTIONS_PER_PAGE;
      return rows.slice(start, start + TRANSACTIONS_PER_PAGE);
    });

    const toggleTransactionSort = (key) => {
      if (transactionSort.key === key) {
        transactionSort.direction = transactionSort.direction === 'asc' ? 'desc' : 'asc';
        return;
      }
      transactionSort.key = key;
      transactionSort.direction = key === 'amount_cents' ? 'desc' : 'asc';
    };

    const transactionSortMarker = (key) => {
      if (transactionSort.key !== key) return '';
      return transactionSort.direction === 'asc' ? '↑' : '↓';
    };

    const filteredTransactionCount = computed(() => filteredTransactions.value.length);

    const transactionRangeStart = computed(() => {
      if (!filteredTransactionCount.value) return 0;
      return (currentTransactionPage.value - 1) * TRANSACTIONS_PER_PAGE + 1;
    });

    const transactionRangeEnd = computed(() => {
      if (!filteredTransactionCount.value) return 0;
      return Math.min(
        filteredTransactionCount.value,
        currentTransactionPage.value * TRANSACTIONS_PER_PAGE
      );
    });

    const goToTransactionPage = (page) => {
      const nextPage = Math.min(Math.max(page, 1), totalTransactionPages.value);
      currentTransactionPage.value = nextPage;
    };

    const goToPreviousTransactionPage = () => goToTransactionPage(currentTransactionPage.value - 1);

    const goToNextTransactionPage = () => goToTransactionPage(currentTransactionPage.value + 1);

    const transactionPageButtons = computed(() => {
      const total = totalTransactionPages.value;
      if (total <= 7) {
        return Array.from({ length: total }, (_, index) => index + 1);
      }

      const start = Math.max(1, currentTransactionPage.value - 2);
      const end = Math.min(total, start + 4);
      const windowStart = Math.max(1, end - 4);
      return Array.from({ length: end - windowStart + 1 }, (_, index) => windowStart + index);
    });

    // ── Copy Functions ───────────────────────────────────────────────────────
    const copyReport = async () => {
      try {
        await navigator.clipboard.writeText(reportText.value);
        copyLabel.value = 'Copied ✓';
        setTimeout(() => {
          copyLabel.value = 'Copy to clipboard';
        }, 2000);
      } catch {
        copyLabel.value = 'Copy failed';
        setTimeout(() => {
          copyLabel.value = 'Copy to clipboard';
        }, 2000);
      }
    };

    const copyPivotTable = async () => {
      if (!pivot.value) return;
      const markdown = toMarkdownTable(
        ['Category', 'Count', 'Share', 'Total', 'Weekly Avg', 'Monthly Avg', 'Yearly Avg'],
        pivot.value.categories.map((row) => [
          row.category,
          row.txn_count,
          `${Math.round(row.share * 100)}%`,
          formatCurrency(row.total_cents),
          formatCurrency(row.weekly_avg_cents),
          formatCurrency(row.monthly_avg_cents),
          formatCurrency(row.yearly_avg_cents),
        ])
      );
      try {
        await navigator.clipboard.writeText(markdown);
        pivotCopyLabel.value = 'OK';
        setTimeout(() => {
          pivotCopyLabel.value = 'MD';
        }, 2000);
      } catch {
        pivotCopyLabel.value = 'ERR';
        setTimeout(() => {
          pivotCopyLabel.value = 'MD';
        }, 2000);
      }
    };

    const copyTransactionsTable = async () => {
      const markdown = toMarkdownTable(
        ['Date', 'Account', 'Description', 'Merchant', 'Category', 'Amount'],
        sortedTransactions.value.map((row) => [
          row.booking_date,
          row.account,
          row.description,
          row.merchant,
          row.category,
          formatCurrency(row.amount_cents),
        ])
      );
      try {
        await navigator.clipboard.writeText(markdown);
        transactionsCopyLabel.value = 'OK';
        setTimeout(() => {
          transactionsCopyLabel.value = 'MD';
        }, 2000);
      } catch {
        transactionsCopyLabel.value = 'ERR';
        setTimeout(() => {
          transactionsCopyLabel.value = 'MD';
        }, 2000);
      }
    };

    // ── Import Functions ────────────────────────────────────────────────────
    const handleDragOver = (event) => {
      event.preventDefault();
      importState.isDragging = true;
    };

    const handleDragLeave = () => {
      importState.isDragging = false;
    };

    const handleDrop = async (event) => {
      event.preventDefault();
      importState.isDragging = false;

      const files = Array.from(event.dataTransfer.files);
      if (files.length > 0) {
        await uploadFiles(files);
      }
    };

    const handleFileSelect = async (event) => {
      const files = Array.from(event.target.files);
      if (files.length > 0) {
        await uploadFiles(files);
      }
      event.target.value = ''; // Reset input
    };

    const uploadFiles = async (files) => {
      importState.isUploading = true;
      importState.error = null;
      importState.lastResult = null;

      try {
        // Upload files sequentially
        const results = [];
        for (const file of files) {
          const result = await uploadCsv(file);
          results.push(result);
        }
        importState.lastResult = results.length === 1 ? results[0] : results;

        // Refresh accounts list and meta
        await Promise.all([loadAccounts(), refreshMeta()]);
      } catch (error) {
        importState.error = error.message;
      } finally {
        importState.isUploading = false;
      }
    };

    // ── Accounts Functions ──────────────────────────────────────────────────
    const loadAccounts = async () => {
      accountsLoading.value = true;
      try {
        const data = await fetchAccounts();
        accountsList.value = data.accounts;
      } finally {
        accountsLoading.value = false;
      }
    };

    const refreshMeta = async () => {
      const m = await fetchMeta();
      meta.accounts = m.accounts;
      meta.min_date = m.min_date;
      meta.max_date = m.max_date;
    };

    const startEditingAccount = (account) => {
      editingAccountId.value = account.id;
      editingAccountName.value = account.display_name || '';
    };

    const cancelEditingAccount = () => {
      editingAccountId.value = null;
      editingAccountName.value = '';
    };

    const saveAccountName = async (accountId) => {
      try {
        await updateAccount(accountId, { display_name: editingAccountName.value || null });
        await Promise.all([loadAccounts(), refreshMeta()]);
        cancelEditingAccount();
      } catch (error) {
        console.error('Failed to update account:', error);
      }
    };

    // ── Rules Functions ─────────────────────────────────────────────────────
    const loadRules = async () => {
      rulesState.loading = true;
      rulesState.error = null;
      try {
        const data = await fetchRules();
        rulesState.path = data.path;
        rulesState.directory = data.directory;
        rulesState.exists = data.exists;
        rulesState.content = data.content || '';
        rulesState.originalContent = data.content || '';
      } catch (error) {
        rulesState.error = error.message;
      } finally {
        rulesState.loading = false;
      }
    };

    const saveRulesContent = async () => {
      rulesState.saving = true;
      rulesState.error = null;
      rulesState.saveMessage = null;
      try {
        await saveRules(rulesState.content);
        rulesState.originalContent = rulesState.content;
        rulesState.saveMessage = 'Saved successfully';
        // Run classification after saving
        await runClassification();
      } catch (error) {
        rulesState.error = error.message;
      } finally {
        rulesState.saving = false;
      }
    };

    const runClassification = async () => {
      rulesState.running = true;
      rulesState.logs = [];
      rulesState.stats = null;
      try {
        const result = await runRules();
        rulesState.logs = result.logs || [];
        rulesState.stats = result.stats;
        if (result.status === 'error') {
          rulesState.error = 'Classification failed - see logs below';
        }
      } catch (error) {
        rulesState.error = error.message;
        rulesState.logs = [{ level: 'error', message: error.message }];
      } finally {
        rulesState.running = false;
      }
    };

    const reloadRules = async () => {
      await loadRules();
    };

    const rulesHasChanges = computed(() => {
      return rulesState.content !== rulesState.originalContent;
    });

    const loadCategoryOptions = async () => {
      const result = await fetchCategoryOptions(filters, searchQuery.value);
      availableCategories.value = result.categories || [];
    };

    const selectorState = computed(() => ({
      filters,
      meta,
      yearButtons: yearButtons.value,
      monthShortcutYear: monthShortcutYear.value,
      selectedCategory: selectedCategory.value,
      categoryBreadcrumbs: categoryBreadcrumbs.value,
      nextCategoryOptions: nextCategoryOptions.value,
      categorySelectValue: categorySelectValue.value,
      searchQuery: searchQuery.value,
    }));

    const selectorActions = {
      updateFrom: (value) => {
        filters.from = value;
      },
      updateTo: (value) => {
        filters.to = value;
      },
      updateCategorySelectValue: (value) => {
        categorySelectValue.value = value;
      },
      updateSearchQuery: (value) => {
        searchQuery.value = value;
      },
      setYear,
      setAll,
      setMonth,
      setYearAllMonths,
      isActiveYear,
      isActiveMonth,
      toggleAccount,
      applyCategorySelection,
      clearSelection,
    };

    // ── Watchers ─────────────────────────────────────────────────────────────
    watch(selectedCategory, () => {
      categorySelectValue.value = '';
    });

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
      } else if (view.value === 'import') {
        // Reset import state when entering import view
        importState.lastResult = null;
        importState.error = null;
      } else if (view.value === 'rules') {
        await loadRules();
      } else {
        loadCurrentViewData();
      }
    });

    watch(searchQuery, () => {
      if (isHydratingFromUrl) return;
      loadCategoryOptions();
      loadCurrentViewData({ resetTransactionsPage: true });
    });

    watch(totalTransactionPages, (pageCount) => {
      if (currentTransactionPage.value > pageCount) {
        currentTransactionPage.value = pageCount;
      }
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

      // Import
      importState,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      handleFileSelect,

      // Accounts
      accountsList,
      accountsLoading,
      loadAccounts,
      editingAccountId,
      editingAccountName,
      startEditingAccount,
      cancelEditingAccount,
      saveAccountName,

      // Rules
      rulesState,
      loadRules,
      saveRulesContent,
      runClassification,
      reloadRules,
      rulesHasChanges,
    };
  },
}).mount('#app');
