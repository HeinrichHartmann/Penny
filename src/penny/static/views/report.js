import { computed, ref } from 'vue/dist/vue.esm-bundler.js';

import { formatCurrency, toMarkdownTable } from '../utils/format.js';

export const createReportViewState = ({ breakout, pivot, reportText }) => {
  const copyLabel = ref('Copy to clipboard');
  const pivotCopyLabel = ref('MD');

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

  return {
    copyLabel,
    pivotCopyLabel,
    breakoutNet,
    breakoutNetByPeriod,
    copyReport,
    copyPivotTable,
  };
};
