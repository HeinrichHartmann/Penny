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
import { fetchMeta, createApi } from './api.js';
import { createChartManager } from './charts.js';
import { DateFilterPanel } from './components/DateFilterPanel.js';

createApp({
  components: {
    DateFilterPanel,
  },
  setup() {
    // ── State ────────────────────────────────────────────────────────────────
    const view = ref('report');
    const meta = reactive({ accounts: [], min_date: '', max_date: '' });
    const filters = reactive({
      from: '',
      to: '',
      accounts: [],
      neutralize: true,
    });
    const tab = ref('expense');
    const summary = ref(null);
    const tree = ref(null);
    const pivot = ref(null);
    const cashflow = ref(null);
    const breakout = ref(null);
    const breakoutGranularityMode = ref('auto');
    const breakoutShowIncome = ref(true);
    const breakoutShowExpenses = ref(true);
    const pivotDepth = ref('1');
    const transactions = ref(null);
    const selectedCategory = ref(null);
    const yearButtons = ref([]);
    const categoryColorMap = reactive({});
    const reportText = ref('');
    const copyLabel = ref('Copy to clipboard');
    const pivotCopyLabel = ref('MD');
    const transactionsCopyLabel = ref('MD');
    const searchQuery = ref('');
    const transactionListEl = ref(null);
    const visibleTransactionCount = ref(250);
    const transactionSort = reactive({ key: 'booking_date', direction: 'desc' });
    const monthRangeAnchor = ref(null);
    let searchTimer = null;
    const TRANSACTION_BATCH_SIZE = 250;

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

    // ── Transaction Window ───────────────────────────────────────────────────
    const resetTransactionWindow = () => {
      visibleTransactionCount.value = TRANSACTION_BATCH_SIZE;
      nextTick(() => {
        if (transactionListEl.value) transactionListEl.value.scrollTop = 0;
      });
    };

    // ── API ──────────────────────────────────────────────────────────────────
    const api = createApi({
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
      resetTransactionWindow,
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

    // ── Account Toggle ───────────────────────────────────────────────────────
    const toggleAccount = (account) => {
      const index = filters.accounts.indexOf(account);
      if (index === -1) {
        filters.accounts.push(account);
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

    const applyCategorySelection = async (category) => {
      selectedCategory.value = category;
      searchQuery.value = '';
      if (tab.value === 'expense' || tab.value === 'income') {
        await Promise.all([loadTree(), loadPivot(), loadTransactions()]);
        return;
      }
      if (tab.value === 'cashflow') {
        await Promise.all([loadCashflow(), loadTransactions()]);
        return;
      }
      if (tab.value === 'breakout') {
        await Promise.all([loadBreakout(), loadTransactions()]);
        return;
      }
      await loadTransactions();
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

    const sortedTransactions = computed(() => {
      const rows = [...(transactions.value?.transactions || [])];
      const { key, direction } = transactionSort;
      const factor = direction === 'asc' ? 1 : -1;
      rows.sort((left, right) => {
        const primary = compareValues(left[key], right[key]) * factor;
        if (primary !== 0) return primary;
        return compareValues(left.fp, right.fp);
      });
      return rows;
    });

    const visibleTransactions = computed(() => {
      const rows = sortedTransactions.value;
      return rows.slice(0, visibleTransactionCount.value);
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

    const growTransactionWindow = () => {
      const rows = transactions.value?.transactions || [];
      if (visibleTransactionCount.value >= rows.length) return;
      visibleTransactionCount.value = Math.min(
        rows.length,
        visibleTransactionCount.value + TRANSACTION_BATCH_SIZE
      );
    };

    const onTransactionScroll = (event) => {
      const el = event.target;
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 160) {
        growTransactionWindow();
      }
    };

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

    // ── Watchers ─────────────────────────────────────────────────────────────
    watch(
      () => [filters.from, filters.to, filters.accounts.join(','), filters.neutralize],
      () => {
        loadAll();
      }
    );

    watch(tab, () => {
      if (tab.value === 'cashflow') {
        loadCashflow();
        loadTransactions();
      } else if (tab.value === 'breakout') {
        loadBreakout();
        loadTransactions();
      } else if (tab.value === 'report') {
        loadReport();
      } else {
        loadTree();
        loadPivot();
        loadTransactions();
      }
    });

    watch(searchQuery, () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadTransactions(), 250);
    });

    watch(pivotDepth, () => {
      if (tab.value === 'expense' || tab.value === 'income') loadPivot();
    });

    watch(breakoutGranularityMode, () => {
      if (tab.value === 'breakout') loadBreakout();
    });

    watch([breakoutShowIncome, breakoutShowExpenses], () => {
      if (tab.value === 'breakout') renderBreakout();
    });

    // ── Init ─────────────────────────────────────────────────────────────────
    onMounted(async () => {
      const m = await fetchMeta();
      meta.accounts = m.accounts;
      meta.min_date = m.min_date;
      meta.max_date = m.max_date;

      yearButtons.value = computeYearButtons(m.min_date, m.max_date);

      const defaultRange = computeDefaultDateRange(m.max_date);
      filters.from = defaultRange.from;
      filters.to = defaultRange.to;
      filters.accounts = [...m.accounts];
      filters.neutralize = true;
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
      transactionListEl,
      visibleTransactionCount,
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
      visibleTransactions,
      toggleTransactionSort,
      transactionSortMarker,
      onTransactionScroll,
      growTransactionWindow,

      // Copy
      copyReport,
      copyPivotTable,
      copyTransactionsTable,
    };
  },
}).mount('#app');
