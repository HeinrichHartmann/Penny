/**
 * Balance view state management
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
export const createBalanceViewState = ({ fetchAccountValueHistory, filters }) => {
  const valueHistory = ref(null);
  const loading = ref(false);
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
    return points[points.length - 1].balance_cents;
  });

  const loadValueHistory = async () => {
    if (!filters.accounts || filters.accounts.length === 0) {
      valueHistory.value = null;
      return;
    }

    loading.value = true;
    try {
      const data = await fetchAccountValueHistory(filters);
      valueHistory.value = data;
      renderBalanceChart();
    } catch (error) {
      console.error('Failed to load value history:', error);
      valueHistory.value = null;
    } finally {
      loading.value = false;
    }
  };

  const renderBalanceChart = () => {
    if (!balanceChartEl.value || !valueHistory.value) return;

    if (balanceChart && balanceChart.getDom() !== balanceChartEl.value) {
      balanceChart.dispose();
      balanceChart = null;
    }

    if (!balanceChart) {
      balanceChart = echarts.init(balanceChartEl.value);
    }

    const valuePoints = valueHistory.value.value_points || [];
    const volumePoints = valueHistory.value.volume_points || [];

    if (valuePoints.length === 0) {
      balanceChart.clear();
      return;
    }

    // Prepare data for the line chart (account value)
    const dates = valuePoints.map(p => p.date);
    const balances = valuePoints.map(p => p.balance_cents);
    const snapshotFlags = valuePoints.map(p => p.is_snapshot);

    // Prepare data for volume bars (optional)
    const volumeData = showVolume.value
      ? volumePoints.map(p => {
          const inflow = p.inflow_cents || 0;
          const outflow = p.outflow_cents || 0;
          return { inflow, outflow };
        })
      : [];

    // Build series
    const series = [
      {
        name: 'Account Balance',
        type: 'line',
        data: balances,
        smooth: false,
        symbol: (value, params) => {
          // Use different symbol for snapshot points
          return snapshotFlags[params.dataIndex] ? 'circle' : 'none';
        },
        symbolSize: (value, params) => {
          return snapshotFlags[params.dataIndex] ? 8 : 4;
        },
        itemStyle: {
          color: '#845b31',
        },
        lineStyle: {
          width: 2,
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
              { offset: 0, color: 'rgba(132, 91, 49, 0.3)' },
              { offset: 1, color: 'rgba(132, 91, 49, 0.05)' }
            ]
          }
        },
        yAxisIndex: 0,
      },
    ];

    // Add volume bars if enabled
    if (showVolume.value && volumePoints.length > 0) {
      // Map volume data to dates
      const volumeByDate = {};
      volumePoints.forEach(p => {
        volumeByDate[p.date] = p;
      });

      const inflowData = dates.map(date => volumeByDate[date]?.inflow_cents || 0);
      const outflowData = dates.map(date => -(volumeByDate[date]?.outflow_cents || 0));

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
            let result = `${params[0].name}<br/>`;
            params.forEach(p => {
              if (p.seriesName === 'Account Balance') {
                result += `${p.seriesName}: ${formatCurrency(p.value)}`;
                const idx = p.dataIndex;
                if (snapshotFlags[idx]) {
                  result += ' 📌';
                }
                result += '<br/>';
              } else {
                result += `${p.seriesName}: ${formatCurrency(Math.abs(p.value))}<br/>`;
              }
            });
            return result;
          },
        },
        legend: {
          data: series.map(s => s.name),
          top: 6,
        },
        grid: {
          left: 80,
          right: showVolume.value ? 80 : 24,
          top: 48,
          bottom: 52,
          containLabel: false,
        },
        xAxis: {
          type: 'category',
          data: dates,
          axisTick: { alignWithLabel: true },
        },
        yAxis: yAxis,
        series: series,
      },
      true
    );
  };

  return {
    valueHistory,
    loading,
    showVolume,
    latestBalance,
    setBalanceChartEl,
    setShowVolume,
    loadValueHistory,
    renderBalanceChart,
  };
};
