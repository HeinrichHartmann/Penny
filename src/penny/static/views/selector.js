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
    previewCategorySelection,
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
