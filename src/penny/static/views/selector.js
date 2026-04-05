import { computed, ref, watch } from 'vue/dist/vue.esm-bundler.js';

export const createSelectorState = ({
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
}) => {
  const selectorCategory = ref(selectedCategory.value);
  const categorySelectValue = ref('');
  const availableCategories = ref([]);
  let searchReloadTimer = null;
  let filterReloadTimer = null;

  const reloadCurrentView = async ({ resetPage = true } = {}) => {
    await loadCategoryOptions();
    if (view.value === 'transactions') {
      await loadTransactionsForCurrentView({ resetPage });
      return;
    }
    if (view.value === 'report') {
      await loadAll();
    }
  };

  const scheduleFilterReload = ({ resetPage = true, delayMs = 0 } = {}) => {
    if (filterReloadTimer) {
      clearTimeout(filterReloadTimer);
    }
    filterReloadTimer = setTimeout(async () => {
      await reloadCurrentView({ resetPage });
    }, delayMs);
  };

  const selectedMatchesCategory = (category) => {
    if (!selectedCategory.value || !category) return false;
    return (
      selectedCategory.value === category ||
      selectedCategory.value.startsWith(`${category}/`)
    );
  };

  const categoryBreadcrumbs = computed(() => {
    if (!selectorCategory.value) return [];
    const parts = selectorCategory.value.split('/').filter(Boolean);
    return parts.map((label, index) => ({
      label,
      path: parts.slice(0, index + 1).join('/'),
    }));
  });

  const nextCategoryOptions = computed(() => {
    const options = new Map();
    const prefix = selectorCategory.value ? `${selectorCategory.value}/` : '';

    for (const category of availableCategories.value) {
      if (!category) continue;
      if (selectorCategory.value && !category.startsWith(prefix)) continue;

      const remainder = selectorCategory.value ? category.slice(prefix.length) : category;
      if (!remainder) continue;

      const nextSegment = remainder.split('/')[0];
      if (!nextSegment) continue;

      const path = selectorCategory.value
        ? `${selectorCategory.value}/${nextSegment}`
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

  const loadCategoryOptions = async () => {
    const result = await fetchCategoryOptions(filters, searchQuery.value);
    availableCategories.value = result.categories || [];
  };

  const applyCategorySelection = async (category) => {
    selectorCategory.value = category;
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
    void applyCategorySelection(null);
  };

  const previewCategorySelection = (category) => {
    selectorCategory.value = category;
  };

  const selectorState = computed(() => ({
    filters,
    meta,
    yearButtons: yearButtons.value,
    monthShortcutYear: monthShortcutYear.value,
    selectedCategory: selectorCategory.value,
    categoryBreadcrumbs: categoryBreadcrumbs.value,
    nextCategoryOptions: nextCategoryOptions.value,
    categorySelectValue: categorySelectValue.value,
    searchQuery: searchQuery.value,
  }));

  const selectorActions = {
    updateFrom: (value) => {
      filters.from = value;
      scheduleFilterReload({ resetPage: true, delayMs: 150 });
    },
    updateTo: (value) => {
      filters.to = value;
      scheduleFilterReload({ resetPage: true, delayMs: 150 });
    },
    updateCategorySelectValue: (value) => {
      categorySelectValue.value = value;
    },
    updateSearchQuery: (value) => {
      searchQuery.value = value;
      if (searchReloadTimer) {
        clearTimeout(searchReloadTimer);
      }
      searchReloadTimer = setTimeout(async () => {
        await loadCategoryOptions();
        if (view.value === 'transactions') {
          await loadTransactionsForCurrentView({ resetPage: true });
          return;
        }
        if (view.value === 'report') {
          await loadAll();
        }
      }, 150);
    },
    setYear,
    setAll,
    setMonth,
    setYearAllMonths,
    isActiveYear,
    isActiveMonth,
    toggleAccount: (accountId) => {
      toggleAccount(accountId);
      scheduleFilterReload({ resetPage: true });
    },
    applyCategorySelection,
    clearSelection,
    previewCategorySelection,
  };

  selectorActions.setYear = (year) => {
    setYear(year);
    scheduleFilterReload({ resetPage: true });
  };

  selectorActions.setAll = () => {
    setAll();
    scheduleFilterReload({ resetPage: true });
  };

  selectorActions.setMonth = (event, month) => {
    setMonth(event, month);
    scheduleFilterReload({ resetPage: true });
  };

  selectorActions.setYearAllMonths = () => {
    setYearAllMonths();
    scheduleFilterReload({ resetPage: true });
  };

  watch(selectorCategory, () => {
    categorySelectValue.value = '';
  });

  return {
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
  };
};
