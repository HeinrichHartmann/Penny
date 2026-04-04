export const readUrlState = () => {
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

export const syncUrlState = ({
  view,
  tab,
  filters,
  selectedCategory,
  searchQuery,
  pivotDepth,
  breakoutGranularityMode,
  breakoutShowIncome,
  breakoutShowExpenses,
  currentTransactionPage,
}) => {
  const params = new URLSearchParams();
  params.set('view', view);
  params.set('tab', tab);

  if (filters.from) params.set('from', filters.from);
  if (filters.to) params.set('to', filters.to);
  params.set('accounts', filters.accounts.join(','));
  params.set('neutralize', String(filters.neutralize));

  if (selectedCategory) params.set('category', selectedCategory);
  if (searchQuery) params.set('q', searchQuery);

  params.set('pivotDepth', pivotDepth);
  params.set('breakoutGranularityMode', breakoutGranularityMode);
  params.set('breakoutShowIncome', String(breakoutShowIncome));
  params.set('breakoutShowExpenses', String(breakoutShowExpenses));
  params.set('transactionPage', String(currentTransactionPage));

  const query = params.toString();
  const nextUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState(null, '', nextUrl);
};
