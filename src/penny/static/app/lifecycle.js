export const setupAppLifecycle = ({
  watch,
  onMounted,
  isHydrating,
  setHydrating,
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
}) => {
  watch(
    () => [filters.from, filters.to, filters.accounts.join(','), filters.neutralize],
    () => {
      loadCategoryOptions();
      loadCurrentViewData({ resetTransactionsPage: true });
    }
  );

  watch(tab, () => {
    if (isHydrating() || view.value !== 'report') return;
    loadAll();
  });

  watch(view, async () => {
    if (view.value !== 'accounts') {
      loadCurrentViewData();
    }
  });

  watch(searchQuery, () => {
    if (isHydrating()) return;
    loadCategoryOptions();
    loadCurrentViewData({ resetTransactionsPage: true });
  });

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
    syncUrl
  );

  watch(pivotDepth, () => {
    if (isHydrating() || view.value !== 'report') return;
    if (tab.value === 'expense' || tab.value === 'income') loadPivot();
  });

  watch(breakoutGranularityMode, () => {
    if (isHydrating() || view.value !== 'report') return;
    if (tab.value === 'breakout') loadBreakout();
  });

  watch([breakoutShowIncome, breakoutShowExpenses], () => {
    if (isHydrating() || view.value !== 'report') return;
    if (tab.value === 'breakout') renderBreakout();
  });

  onMounted(async () => {
    await initializeAppState({
      fetchMeta,
      initialUrlState,
      meta,
      filters,
      yearButtons,
    });

    setHydrating(false);
    await loadCategoryOptions();
    syncUrl();
    await loadCurrentViewData();
  });
};
