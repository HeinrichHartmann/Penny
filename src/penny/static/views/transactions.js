import { computed, reactive, ref, watch } from 'vue/dist/vue.esm-bundler.js';

import { formatCurrency, toMarkdownTable } from '../utils/format.js';

const TRANSACTIONS_PER_PAGE = 100;

export const createTransactionsViewState = ({ transactions, initialPage }) => {
  const transactionsCopyLabel = ref('MD');
  const currentTransactionPage = ref(Math.max(1, parseInt(initialPage || '1', 10) || 1));
  const transactionSort = reactive({ key: 'booking_date', direction: 'desc' });

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

  const resetTransactionPagination = () => {
    currentTransactionPage.value = 1;
  };

  const filteredTransactions = computed(() => transactions.value?.transactions || []);

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

  watch(totalTransactionPages, (pageCount) => {
    if (currentTransactionPage.value > pageCount) {
      currentTransactionPage.value = pageCount;
    }
  });

  return {
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
  };
};
