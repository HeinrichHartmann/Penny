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
    const balanceData = valuePoints.map(p => [p.date, p.total_balance]);

    // Track which points are anchors (for FAT dots)
    const anchorFlags = valuePoints.map(p => p.is_anchor || false);

    // Create lookup map from date to delta for inconsistencies
    const deltaMap = {};
    inconsistencies.forEach(inc => {
      deltaMap[inc.date] = inc.delta_cents;
    });

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
        // Show symbols ONLY on anchor dates (FAT dots)
        showSymbol: true,
        symbol: (value, params) => {
          return anchorFlags[params.dataIndex] ? 'circle' : 'none';
        },
        symbolSize: (value, params) => {
          return anchorFlags[params.dataIndex] ? 12 : 0;
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
            // With time axis, value is [date, amount]
            const date = params[0].value[0];
            const dataIndex = params[0].dataIndex;
            const isAnchor = anchorFlags[dataIndex];
            const delta = deltaMap[date];

            let result = `${date}`;
            if (isAnchor) {
              result += ' 📍'; // Pin emoji for anchor
            }
            result += '<br/>';

            params.forEach(p => {
              const amount = Array.isArray(p.value) ? p.value[1] : p.value;
              if (p.seriesName === 'Account Balance') {
                result += `${p.seriesName}: ${formatCurrency(amount)}<br/>`;
              } else {
                result += `${p.seriesName}: ${formatCurrency(Math.abs(amount))}<br/>`;
              }
            });

            // ALWAYS show Delta line (for debugging/verification)
            if (isAnchor) {
              if (delta !== undefined) {
                const deltaSign = delta >= 0 ? '+' : '';
                result += `Delta: ${deltaSign}${formatCurrency(delta)}<br/>`;
              } else {
                result += `Delta: €0.00 (no inconsistency)<br/>`;
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
