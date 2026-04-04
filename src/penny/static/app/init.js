import { computeDefaultDateRange, computeYearButtons } from '../utils/date.js';

export const initializeAppState = async ({
  fetchMeta,
  initialUrlState,
  meta,
  filters,
  yearButtons,
}) => {
  const m = await fetchMeta();
  meta.accounts = m.accounts;
  meta.min_date = m.min_date;
  meta.max_date = m.max_date;

  yearButtons.value = computeYearButtons(m.min_date, m.max_date);

  const defaultRange = computeDefaultDateRange(m.max_date);
  filters.from = initialUrlState.from || defaultRange.from;
  filters.to = initialUrlState.to || defaultRange.to;

  const allAccountIds = m.accounts.map((acc) => acc.id);
  filters.accounts = initialUrlState.accounts
    ? initialUrlState.accounts.map(Number).filter((id) => allAccountIds.includes(id))
    : [...allAccountIds];
  filters.neutralize = initialUrlState.neutralize == null
    ? true
    : initialUrlState.neutralize !== 'false';
};
