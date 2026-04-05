import { computed, ref, watch } from 'vue/dist/vue.esm-bundler.js';

export const createSelectorState = ({
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
}) => {
  // ADR-013: selector interactions only mutate root-owned app state.
  // Data loading happens in app.js via root watchers and rehydration.
  const selectorCategory = ref(selectedCategory.value);
  const categorySelectValue = ref('');

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

    for (const category of categoryOptions.value) {
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

  const applyCategorySelection = (category) => {
    selectorCategory.value = category;
    selectedCategory.value = category;
  };

  const clearSelection = () => {
    applyCategorySelection(null);
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

  watch(selectedCategory, (value) => {
    selectorCategory.value = value;
  });

  watch(selectorCategory, () => {
    categorySelectValue.value = '';
  });

  return {
    selectorCategory,
    categorySelectValue,
    selectedMatchesCategory,
    categoryBreadcrumbs,
    nextCategoryOptions,
    applyCategorySelection,
    clearSelection,
    previewCategorySelection,
    selectorState,
    selectorActions,
  };
};
