/**
 * Balance view state management
 *
 * IMPORTANT: ALL MATH MUST BE DONE IN THE BACKEND.
 * This view is ONLY for displaying data 1:1 as provided by the API.
 * No aggregation, calculations, or data transformations here.
 */
import { computed, ref } from 'vue/dist/vue.esm-bundler.js';
import * as echarts from 'echarts';
import { PALETTE } from '../utils/color.js';
import { formatCurrency } from '../utils/format.js';

/**
 * Create balance view state.
 * @param {object} options
 * @returns {object} State and actions
 */
export const createBalanceViewState = ({
  valueHistory,
  loading,
  loadValueHistory,
  onDateRangeChange,
}) => {
  const dayStartTimestamp = (dateStr) => new Date(`${dateStr}T00:00:00`).getTime();
  const nextDayTimestamp = (dateStr) => dayStartTimestamp(dateStr) + (24 * 60 * 60 * 1000);

  const balanceChartEl = ref(null);
  let balanceChart = null;

  const setBalanceChartEl = (el) => {
    balanceChartEl.value = el;
  };

  const latestBalance = computed(() => {
    if (!valueHistory.value || !valueHistory.value.value_points) return null;
    const points = valueHistory.value.value_points;
    if (points.length === 0) return null;
    return points[points.length - 1].total_balance;
  });

  const resetValueHistory = () => {
    valueHistory.value = null;
    loading.value = false;
  };

  const renderBalanceChart = () => {
    if (!balanceChartEl.value || !valueHistory.value) return;

    if (balanceChart && balanceChart.getDom() !== balanceChartEl.value) {
      balanceChart.dispose();
      balanceChart = null;
    }

    if (!balanceChart) {
      balanceChart = echarts.init(balanceChartEl.value);

      // Listen to brush selection and update global date filters
      balanceChart.on('brushEnd', (params) => {
        if (!params.areas || params.areas.length === 0) return;

        const area = params.areas[0];
        if (!area.coordRange) return;

        // coordRange contains [startTimestamp, endTimestamp] for time axis
        const [startTime, endTime] = area.coordRange;

        // Convert timestamps to date strings (YYYY-MM-DD)
        const startDate = new Date(startTime).toISOString().split('T')[0];
        const endDate = new Date(endTime).toISOString().split('T')[0];

        if (startDate && endDate && onDateRangeChange) {
          onDateRangeChange(startDate, endDate);
        }

        // Clear the brush selection and re-enable brush mode
        balanceChart.dispatchAction({
          type: 'brush',
          areas: [],
        });
        // Re-activate brush for next selection
        balanceChart.dispatchAction({
          type: 'takeGlobalCursor',
          key: 'brush',
          brushOption: {
            brushType: 'lineX',
          },
        });
      });
    }

    const valuePoints = valueHistory.value.value_points || [];
    const inconsistencies = valueHistory.value.inconsistencies || [];
    const dates = valueHistory.value.dates || [];
    const accountColumns = valueHistory.value.account_columns || {};
    const accountNames = valueHistory.value.account_names || {};
    const todayIdx = valueHistory.value.today_idx;

    if (valuePoints.length === 0) {
      balanceChart.clear();
      return;
    }

    // Data is already aggregated to one point per day from backend
    // Tie deltas to the same date-indexed points as the main balance line.
    const deltaByDate = {};
    inconsistencies.forEach(inc => {
      deltaByDate[inc.date] = inc;
    });
    const chartPointByDate = {};
    valuePoints.forEach(point => {
      chartPointByDate[point.date] = {
        date: point.date,
        totalBalance: point.total_balance,
        isAnchor: point.is_anchor || false,
        inconsistency: deltaByDate[point.date] || null,
      };
    });

    // Build stacked series from account columns
    const accountIds = Object.keys(accountColumns).sort((a, b) => parseInt(a) - parseInt(b));
    const series = [];

    // Consistent color mapping based on account ID (hash-based)
    const getAccountColor = (accId) => {
      const colors = [
        { fill: 'rgba(76, 175, 80, 0.6)', line: 'rgba(76, 175, 80, 0.9)' },    // green
        { fill: 'rgba(33, 150, 243, 0.6)', line: 'rgba(33, 150, 243, 0.9)' },  // blue
        { fill: 'rgba(156, 39, 176, 0.6)', line: 'rgba(156, 39, 176, 0.9)' },  // purple
        { fill: 'rgba(255, 152, 0, 0.6)', line: 'rgba(255, 152, 0, 0.9)' },    // orange
        { fill: 'rgba(0, 188, 212, 0.6)', line: 'rgba(0, 188, 212, 0.9)' },    // cyan
        { fill: 'rgba(233, 30, 99, 0.6)', line: 'rgba(233, 30, 99, 0.9)' },    // pink
        { fill: 'rgba(139, 195, 74, 0.6)', line: 'rgba(139, 195, 74, 0.9)' },  // light green
        { fill: 'rgba(63, 81, 181, 0.6)', line: 'rgba(63, 81, 181, 0.9)' },    // indigo
      ];
      // Use account ID to get consistent color index
      const index = parseInt(accId) % colors.length;
      return colors[index];
    };

    if (accountIds.length > 1 && dates.length > 0) {
      // Multiple accounts: use ECharts built-in stacking
      // Each series provides individual account values, ECharts stacks them automatically
      const anchorDates = new Set(valuePoints.filter(p => p.is_anchor).map(p => p.date));

      accountIds.forEach((accId) => {
        const accBalances = accountColumns[accId] || [];
        const color = getAccountColor(accId);
        const name = accountNames[accId] || `Account #${accId}`;

        // Build data points with individual account values (not cumulative)
        const seriesData = dates.map((date, i) => [date, accBalances[i] || 0]);

        series.push({
          name: name,
          type: 'line',
          stack: 'balance',
          stackStrategy: 'all',
          data: seriesData,
          step: 'end',
          showSymbol: false,
          lineStyle: {
            width: 1,
            color: color.line,
          },
          areaStyle: {
            color: color.fill,
          },
        });
      });

      // Add a separate "Total" line on top (thicker, with anchor markers)
      // This uses value_points which already has total_balance summed
      const totalData = dates.map((date) => {
        const point = valuePoints.find(p => p.date === date);
        return {
          value: [date, point?.total_balance || 0],
          isAnchor: anchorDates.has(date),
        };
      });
      series.push({
        name: 'Total',
        type: 'line',
        data: totalData,
        step: 'end',
        showSymbol: true,
        symbol: (_value, params) => {
          return params.data?.isAnchor ? 'circle' : 'none';
        },
        symbolSize: (_value, params) => {
          return params.data?.isAnchor ? 12 : 0;
        },
        itemStyle: {
          color: '#845b31',
          borderColor: '#fff',
          borderWidth: 2,
        },
        lineStyle: {
          width: 2.5,
          color: '#845b31',
        },
        areaStyle: null, // No fill for total line
        z: 100,
      });
    } else if (accountIds.length === 1 && dates.length > 0) {
      // Single account with column data: use consistent color
      const accId = accountIds[0];
      const color = getAccountColor(accId);
      const name = accountNames[accId] || `Account #${accId}`;
      const accBalances = accountColumns[accId] || [];

      const anchorDates = new Set(valuePoints.filter(p => p.is_anchor).map(p => p.date));
      const balanceData = dates.map((date, i) => ({
        value: [date, accBalances[i] || 0],
        isAnchor: anchorDates.has(date),
      }));

      series.push({
        name: name,
        type: 'line',
        data: balanceData,
        step: 'end',
        showSymbol: true,
        symbol: (_value, params) => {
          return params.data?.isAnchor ? 'circle' : 'none';
        },
        symbolSize: (_value, params) => {
          return params.data?.isAnchor ? 12 : 0;
        },
        itemStyle: {
          color: color.line,
          borderColor: '#fff',
          borderWidth: 2,
        },
        lineStyle: {
          width: 1.5,
          color: color.line,
        },
        areaStyle: {
          color: color.fill,
        },
      });
    } else {
      // Legacy fallback: use original value_points
      const balanceData = [];
      valuePoints.forEach(point => {
        const chartPoint = chartPointByDate[point.date];
        if (chartPoint?.isAnchor && chartPoint?.inconsistency) {
          balanceData.push({
            value: [point.date, chartPoint.inconsistency.projected_balance],
            isAnchor: false,
          });
          balanceData.push({
            value: [point.date, null],
            isAnchor: false,
            isBreak: true,
          });
          balanceData.push({
            value: [point.date, chartPoint.inconsistency.anchor_balance],
            isAnchor: true,
          });
          return;
        }

        balanceData.push({
          value: [point.date, point.total_balance],
          isAnchor: chartPoint?.isAnchor || false,
        });
      });

      const deltaBarData = valuePoints
        .filter(point => chartPointByDate[point.date]?.inconsistency)
        .map(point => {
          const inc = chartPointByDate[point.date].inconsistency;
          return [
            {
              xAxis: dayStartTimestamp(point.date),
              yAxis: Math.min(inc.projected_balance, inc.anchor_balance),
            },
            {
              xAxis: nextDayTimestamp(point.date),
              yAxis: Math.max(inc.projected_balance, inc.anchor_balance),
            },
          ];
        });

      series.push({
        name: 'Account Balance',
        type: 'line',
        data: balanceData,
        step: 'end',
        connectNulls: false,
        showSymbol: true,
        symbol: (_value, params) => {
          return params.data?.isAnchor ? 'circle' : 'none';
        },
        symbolSize: (_value, params) => {
          return params.data?.isAnchor ? 12 : 0;
        },
        itemStyle: {
          color: '#845b31',
          borderColor: '#fff',
          borderWidth: 2,
        },
        lineStyle: {
          width: 1.5,
          color: '#845b31',
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(132, 91, 49, 0.2)' },
              { offset: 1, color: 'rgba(132, 91, 49, 0.02)' }
            ]
          }
        },
        markArea: deltaBarData.length > 0 ? {
          silent: true,
          itemStyle: {
            color: 'rgba(193, 18, 31, 0.82)',
          },
          emphasis: {
            disabled: true,
          },
          data: deltaBarData,
        } : undefined,
        yAxisIndex: 0,
      });
    }

    // Add future overlay (grey area from today onwards)
    if (todayIdx !== null && todayIdx !== undefined && dates[todayIdx]) {
      const futureDate = dates[todayIdx];
      const lastDate = dates[dates.length - 1];
      // Add as a separate series with markArea for the future region
      series.push({
        name: '_future_overlay',
        type: 'line',
        data: [],
        markArea: {
          silent: true,
          itemStyle: {
            color: 'rgba(128, 128, 128, 0.15)',
          },
          data: [[
            { xAxis: futureDate },
            { xAxis: nextDayTimestamp(lastDate) },
          ]],
        },
      });
    }

    const yAxis = [
      {
        type: 'value',
        name: 'Balance',
        position: 'left',
        axisLabel: {
          formatter: (val) => formatCurrency(val),
        },
        splitLine: {
          lineStyle: { color: 'rgba(132, 91, 49, 0.16)' },
        },
      },
    ];

    balanceChart.setOption(
      {
        color: PALETTE,
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross',
          },
          formatter: (params) => {
            const firstValueParam = params.find(
              p => Array.isArray(p.value) && p.value[0]
            );
            if (!firstValueParam) {
              return '';
            }

            const date = firstValueParam.value[0];
            const point = chartPointByDate[date];
            const isAnchor = point?.isAnchor || false;
            const inconsistency = point?.inconsistency || null;
            const delta = inconsistency?.delta_cents;

            let result = `${date}`;
            if (isAnchor) {
              result += ' 📍'; // Pin emoji for anchor
            }
            result += '<br/>';

            if (inconsistency) {
              result += `Projected Balance: ${formatCurrency(inconsistency.projected_balance)}<br/>`;
              result += `Anchor Balance: ${formatCurrency(inconsistency.anchor_balance)}<br/>`;
            } else if (point) {
              result += `Account Balance: ${formatCurrency(point.totalBalance)}<br/>`;
            }

            params.forEach(p => {
              if (p.seriesName === 'Account Balance') {
                return;
              }

              const amount = Array.isArray(p.value) ? p.value[1] : p.value;
              if (amount !== null && amount !== undefined) {
                result += `${p.seriesName}: ${formatCurrency(Math.abs(amount))}<br/>`;
              }
            });

            if (isAnchor) {
              if (delta !== undefined) {
                const deltaSign = delta >= 0 ? '+' : '';
                result += `Delta: ${deltaSign}${formatCurrency(delta)}<br/>`;
              }
            }

            return result;
          },
        },
        legend: {
          data: series.filter(s => !s.name.startsWith('_')).map(s => s.name),
          top: 6,
        },
        dataZoom: [
          {
            type: 'inside',
            xAxisIndex: 0,
            filterMode: 'none',
            zoomOnMouseWheel: true,
            moveOnMouseMove: false,
            moveOnMouseWheel: false,
          },
        ],
        toolbox: {
          show: false,
        },
        brush: {
          xAxisIndex: 0,
          brushType: 'lineX',
          brushMode: 'single',
          brushStyle: {
            borderWidth: 1,
            color: 'rgba(132, 91, 49, 0.2)',
            borderColor: 'rgba(132, 91, 49, 0.8)',
          },
        },
        grid: {
          left: 80,
          right: 24,
          top: 48,
          bottom: 52,
          containLabel: false,
        },
        xAxis: {
          type: 'time',
          axisTick: { alignWithLabel: true },
          axisLabel: {
            formatter: '{yyyy}-{MM}-{dd}',
          },
        },
        yAxis: yAxis,
        series: series,
      },
      true
    );

    // Activate brush tool by default for drag-to-zoom
    balanceChart.dispatchAction({
      type: 'takeGlobalCursor',
      key: 'brush',
      brushOption: {
        brushType: 'lineX',
      },
    });
  };

  return {
    valueHistory,
    loading,
    latestBalance,
    resetValueHistory,
    setBalanceChartEl,
    loadValueHistory,
    renderBalanceChart,
  };
};
