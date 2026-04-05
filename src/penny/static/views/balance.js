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
  filters,
  onDateRangeChange,
}) => {
  const dayStartTimestamp = (dateStr) => new Date(`${dateStr}T00:00:00`).getTime();
  const nextDayTimestamp = (dateStr) => dayStartTimestamp(dateStr) + (24 * 60 * 60 * 1000);

  const showVolume = ref(false);
  const balanceChartEl = ref(null);
  let balanceChart = null;

  const setBalanceChartEl = (el) => {
    balanceChartEl.value = el;
  };

  const setShowVolume = (value) => {
    showVolume.value = value;
    renderBalanceChart();
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
    const volumePoints = valueHistory.value.volume_points || [];
    const inconsistencies = valueHistory.value.inconsistencies || [];

    if (valuePoints.length === 0) {
      balanceChart.clear();
      return;
    }

    // Data is already aggregated to one point per day from backend
    // Tie deltas to the same date-indexed points as the main balance line.
    // This keeps the inconsistency bar anchored to the rendered balance point.
    const deltaByDate = {};
    inconsistencies.forEach(inc => {
      deltaByDate[inc.date] = inc;
    });
    const chartPoints = valuePoints.map(point => ({
      date: point.date,
      totalBalance: point.total_balance,
      isAnchor: point.is_anchor || false,
      inconsistency: deltaByDate[point.date] || null,
    }));
    const chartPointByDate = {};
    chartPoints.forEach(point => {
      chartPointByDate[point.date] = point;
    });
    const balanceData = [];
    chartPoints.forEach(point => {
      if (point.isAnchor && point.inconsistency) {
        balanceData.push({
          value: [point.date, point.inconsistency.projected_balance],
          isAnchor: false,
        });
        balanceData.push({
          value: [point.date, null],
          isAnchor: false,
          isBreak: true,
        });
        balanceData.push({
          value: [point.date, point.inconsistency.anchor_balance],
          isAnchor: true,
        });
        return;
      }

      balanceData.push({
        value: [point.date, point.totalBalance],
        isAnchor: point.isAnchor,
      });
    });
    const deltaBarData = chartPoints
      .filter(point => point.isAnchor && point.inconsistency)
      .map(point => ([
        {
          xAxis: dayStartTimestamp(point.date),
          yAxis: Math.min(
            point.inconsistency.projected_balance,
            point.inconsistency.anchor_balance
          ),
        },
        {
          xAxis: nextDayTimestamp(point.date),
          yAxis: Math.max(
            point.inconsistency.projected_balance,
            point.inconsistency.anchor_balance
          ),
        },
      ]));

    // Prepare data for volume bars (optional)
    const volumeData = showVolume.value
      ? volumePoints.map(p => {
          const inflow = p.inflow_cents || 0;
          const outflow = p.outflow_cents || 0;
          return { inflow, outflow };
        })
      : [];

    // Build series - stepped line chart for date-granularity data
    const series = [
      {
        name: 'Account Balance',
        type: 'line',
        data: balanceData,
        step: 'end',
        connectNulls: false,
        // Show symbols ONLY on anchor dates (FAT dots)
        showSymbol: true,
        symbol: (value, params) => {
          return params.data?.isAnchor ? 'circle' : 'none';
        },
        symbolSize: (value, params) => {
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
      },
    ];

    // Add volume bars if enabled
    if (showVolume.value && volumePoints.length > 0) {
      const inflowData = volumePoints.map(p => [p.date, p.inflow_cents || 0]);
      const outflowData = volumePoints.map(p => [p.date, -(p.outflow_cents || 0)]);

      series.push({
        name: 'Inflow',
        type: 'bar',
        data: inflowData,
        stack: 'volume',
        itemStyle: { color: 'rgba(76, 175, 80, 0.6)' },
        yAxisIndex: 1,
      });

      series.push({
        name: 'Outflow',
        type: 'bar',
        data: outflowData,
        stack: 'volume',
        itemStyle: { color: 'rgba(244, 67, 54, 0.6)' },
        yAxisIndex: 1,
      });
    }

    const yAxis = [
      {
        type: 'value',
        name: 'Balance',
        position: 'left',
        axisLabel: {
          formatter: (value) => formatCurrency(value),
        },
        splitLine: {
          lineStyle: { color: 'rgba(132, 91, 49, 0.16)' },
        },
      },
    ];

    if (showVolume.value) {
      yAxis.push({
        type: 'value',
        name: 'Volume',
        position: 'right',
        axisLabel: {
          formatter: (value) => formatCurrency(Math.abs(value)),
        },
        splitLine: {
          show: false,
        },
      });
    }

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
          data: series.map(s => s.name),
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
          right: showVolume.value ? 80 : 24,
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
    showVolume,
    latestBalance,
    resetValueHistory,
    setBalanceChartEl,
    setShowVolume,
    loadValueHistory,
    renderBalanceChart,
  };
};
