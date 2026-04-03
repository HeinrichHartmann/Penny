/**
 * Date utilities for filter management.
 */

/**
 * Month button definitions for the UI.
 */
export const MONTH_BUTTONS = [
  { value: 1, label: 'Jan' },
  { value: 2, label: 'Feb' },
  { value: 3, label: 'Mar' },
  { value: 4, label: 'Apr' },
  { value: 5, label: 'May' },
  { value: 6, label: 'Jun' },
  { value: 7, label: 'Jul' },
  { value: 8, label: 'Aug' },
  { value: 9, label: 'Sep' },
  { value: 10, label: 'Oct' },
  { value: 11, label: 'Nov' },
  { value: 12, label: 'Dec' },
];

/**
 * Get the number of days in a month.
 * @param {number} year
 * @param {number} month - 1-indexed month
 * @returns {number}
 */
export const daysInMonth = (year, month) => {
  return new Date(year, month, 0).getDate();
};

/**
 * Create date filter helpers bound to reactive filters and meta.
 * @param {object} filters - reactive filter state
 * @param {object} meta - reactive meta state
 * @param {import('vue').Ref<number|null>} monthRangeAnchor - ref for month range selection
 * @returns {object} Date helper functions
 */
export const createDateHelpers = (filters, meta, monthRangeAnchor) => {
  const setYear = (year) => {
    filters.from = `${year}-01-01`;
    filters.to = `${year}-12-31`;
    monthRangeAnchor.value = null;
  };

  const setAll = () => {
    filters.from = meta.min_date;
    filters.to = meta.max_date;
    monthRangeAnchor.value = null;
  };

  const setMonthRange = (year, fromMonth, toMonth) => {
    const startMonth = Math.min(fromMonth, toMonth);
    const endMonth = Math.max(fromMonth, toMonth);
    const fromMm = String(startMonth).padStart(2, '0');
    const toMm = String(endMonth).padStart(2, '0');
    const dd = String(daysInMonth(year, endMonth)).padStart(2, '0');
    filters.from = `${year}-${fromMm}-01`;
    filters.to = `${year}-${toMm}-${dd}`;
  };

  const getMonthShortcutYear = () => {
    if (!filters.from || !filters.to) return null;
    const fromYear = parseInt(filters.from.slice(0, 4), 10);
    const toYear = parseInt(filters.to.slice(0, 4), 10);
    return fromYear === toYear ? fromYear : null;
  };

  const getSelectedMonthRange = () => {
    const year = getMonthShortcutYear();
    if (year == null || !filters.from || !filters.to) return null;
    const fromMonth = parseInt(filters.from.slice(5, 7), 10);
    const toMonth = parseInt(filters.to.slice(5, 7), 10);
    const toDay = parseInt(filters.to.slice(8, 10), 10);
    if (filters.from.slice(8, 10) !== '01') return null;
    if (toDay !== daysInMonth(year, toMonth)) return null;
    return { year, fromMonth, toMonth };
  };

  const setMonth = (event, month) => {
    const year = getMonthShortcutYear();
    if (year == null) return;
    if (event?.shiftKey && monthRangeAnchor.value != null) {
      setMonthRange(year, monthRangeAnchor.value, month);
      return;
    }
    monthRangeAnchor.value = month;
    setMonthRange(year, month, month);
  };

  const setYearAllMonths = () => {
    const year = getMonthShortcutYear();
    if (year == null) {
      setAll();
      return;
    }
    monthRangeAnchor.value = null;
    setYear(year);
  };

  const isActiveMonth = (month) => {
    const range = getSelectedMonthRange();
    if (!range) return false;
    return range.fromMonth <= month && month <= range.toMonth;
  };

  const isActiveYear = (year) => {
    if (!filters.from || !filters.to) return false;
    return (
      parseInt(filters.from.slice(0, 4), 10) === year &&
      parseInt(filters.to.slice(0, 4), 10) === year
    );
  };

  const isFullYearRange = () => {
    if (!filters.from || !filters.to) return false;
    const fromYear = parseInt(filters.from.slice(0, 4), 10);
    const toYear = parseInt(filters.to.slice(0, 4), 10);
    return (
      fromYear === toYear &&
      filters.from === `${fromYear}-01-01` &&
      filters.to === `${toYear}-12-31`
    );
  };

  const isFullMonthRange = () => {
    if (!filters.from || !filters.to) return false;
    const fromYear = parseInt(filters.from.slice(0, 4), 10);
    const toYear = parseInt(filters.to.slice(0, 4), 10);
    const fromMonth = parseInt(filters.from.slice(5, 7), 10);
    const toMonth = parseInt(filters.to.slice(5, 7), 10);
    const dd = String(daysInMonth(fromYear, fromMonth)).padStart(2, '0');
    return (
      fromYear === toYear &&
      fromMonth === toMonth &&
      filters.from === `${fromYear}-${String(fromMonth).padStart(2, '0')}-01` &&
      filters.to === `${toYear}-${String(toMonth).padStart(2, '0')}-${dd}`
    );
  };

  const computeBreakoutGranularity = (mode) => {
    if (mode !== 'auto') return mode;
    if (isFullYearRange()) return 'month';
    if (isFullMonthRange()) return 'week';
    return 'month';
  };

  return {
    setYear,
    setAll,
    setMonthRange,
    setMonth,
    setYearAllMonths,
    isActiveMonth,
    isActiveYear,
    isFullYearRange,
    isFullMonthRange,
    getMonthShortcutYear,
    getSelectedMonthRange,
    computeBreakoutGranularity,
  };
};

/**
 * Get display label for breakout granularity.
 * @param {string} value
 * @returns {string}
 */
export const breakoutGranularityLabel = (value) => {
  return { month: 'Monthly', week: 'Weekly', day: 'Daily' }[value] || value;
};

/**
 * Compute year buttons from date range.
 * @param {string} minDate
 * @param {string} maxDate
 * @returns {number[]}
 */
export const computeYearButtons = (minDate, maxDate) => {
  const minY = parseInt(minDate.slice(0, 4), 10);
  const maxY = parseInt(maxDate.slice(0, 4), 10);
  const years = [];
  for (let y = minY; y <= maxY; y++) years.push(y);
  return years;
};

/**
 * Compute default date range (last complete month).
 * @param {string} maxDate
 * @returns {{ from: string, to: string }}
 */
export const computeDefaultDateRange = (maxDate) => {
  const date = new Date(maxDate);
  const lastMonth = new Date(date.getFullYear(), date.getMonth() - 1, 1);
  const year = lastMonth.getFullYear();
  const month = lastMonth.getMonth() + 1;
  const lastDay = new Date(year, month, 0).getDate();
  return {
    from: `${year}-${String(month).padStart(2, '0')}-01`,
    to: `${year}-${String(month).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`,
  };
};
