/**
 * ECharts rendering utilities.
 */
import * as echarts from 'echarts';
import { PALETTE, TRANSFER_GRAY } from './utils/color.js';
import { formatCurrency } from './utils/format.js';

/**
 * Transform tree data to ECharts format.
 * @param {object} node
 * @returns {Array}
 */
export const treeToECharts = (node) => {
  if (!node || !node.children) return [];
  return node.children.map((l1) => {
    const color = l1.name === 'transfer' ? TRANSFER_GRAY : undefined;
    return {
      name: l1.name,
      value: l1.value,
      itemStyle: color ? { color } : undefined,
      children: (l1.children || []).map((l2) => ({
        name: l2.name === '(uncategorized)' ? l1.name : `${l1.name}/${l2.name}`,
        value: l2.value,
        children: (l2.children || []).map((m) => ({
          name: m.name,
          value: m.value,
        })),
      })),
    };
  });
};

/**
 * Create chart manager for treemap, sankey, and breakout charts.
 * @param {object} options
 * @returns {object} Chart render functions
 */
export const createChartManager = ({
  treemapEl,
  sankeyEl,
  breakoutEl,
  tree,
  cashflow,
  breakout,
  breakoutShowIncome,
  breakoutShowExpenses,
  categoryColorFn,
  onCategorySelect,
}) => {
  let treemapChart = null;
  let sankeyChart = null;
  let breakoutChart = null;

  const renderTreemap = () => {
    if (!treemapEl.value || !tree.value) return;
    if (treemapChart && treemapChart.getDom() !== treemapEl.value) {
      treemapChart.dispose();
      treemapChart = null;
    }
    if (!treemapChart) {
      treemapChart = echarts.init(treemapEl.value);
      treemapChart.on('click', (params) => {
        if (params.treePathInfo && params.treePathInfo.length >= 2) {
          const deepest = params.treePathInfo[params.treePathInfo.length - 1].name;
          onCategorySelect(deepest);
        }
      });
    }
    treemapChart.setOption(
      {
        color: PALETTE,
        tooltip: {
          formatter: (p) => `${p.name}<br/>${formatCurrency(p.value)}`,
        },
        animationDurationUpdate: 200,
        series: [
          {
            type: 'treemap',
            data: treeToECharts(tree.value),
            roam: false,
            leafDepth: 2,
            animationDuration: 200,
            animationDurationUpdate: 200,
            levels: [
              { itemStyle: { borderWidth: 2, borderColor: '#666', gapWidth: 2 } },
              { itemStyle: { borderWidth: 1, borderColor: '#aaa', gapWidth: 1 } },
              { itemStyle: { borderWidth: 0, gapWidth: 0 } },
            ],
            breadcrumb: { show: false },
            label: { show: true, formatter: '{b}' },
          },
        ],
      },
      true
    );
  };

  const renderSankey = () => {
    if (!sankeyEl.value || !cashflow.value) return;
    if (sankeyChart && sankeyChart.getDom() !== sankeyEl.value) {
      sankeyChart.dispose();
      sankeyChart = null;
    }
    if (!sankeyChart) {
      sankeyChart = echarts.init(sankeyEl.value);
      sankeyChart.on('click', (params) => {
        if (params.data && params.data.name && params.data.name !== 'Budget') {
          const raw = params.data.name.replace(/ \((in|out)\)$/, '');
          onCategorySelect(raw);
        }
      });
    }
    const minValue = cashflow.value.total_expense * 0.01;
    const links = cashflow.value.links.filter((l) => l.value >= minValue);
    const nodeNames = new Set();
    links.forEach((l) => {
      nodeNames.add(l.source);
      nodeNames.add(l.target);
    });
    const nodes = [...nodeNames].map((n) => ({ name: n }));

    sankeyChart.setOption(
      {
        color: PALETTE,
        tooltip: {
          formatter: (p) =>
            p.data.source
              ? `${p.data.source} → ${p.data.target}<br/>${formatCurrency(p.data.value)}`
              : `${p.data.name}`,
        },
        series: [
          {
            type: 'sankey',
            data: nodes,
            links: links,
            emphasis: { focus: 'adjacency' },
            label: { show: true, fontSize: 11 },
            lineStyle: { color: 'gradient', curveness: 0.5 },
            layoutIterations: 32,
          },
        ],
      },
      true
    );
  };

  const renderBreakout = () => {
    if (!breakoutEl.value || !breakout.value) return;
    if (breakoutChart && breakoutChart.getDom() !== breakoutEl.value) {
      breakoutChart.dispose();
      breakoutChart = null;
    }
    if (!breakoutChart) {
      breakoutChart = echarts.init(breakoutEl.value);
      breakoutChart.on('click', (params) => {
        if (!params.seriesName) return;
        onCategorySelect(params.seriesName);
      });
    }

    const periods = breakout.value.periods || [];
    const labels = breakout.value.labels || periods;

    const series = (breakout.value.categories || [])
      .map((cat) => {
        const data = cat.values.map((value) => {
          if (value > 0) return breakoutShowIncome.value ? -value : 0;
          if (value < 0) return breakoutShowExpenses.value ? -value : 0;
          return 0;
        });
        return {
          name: cat.name,
          type: 'bar',
          stack: 'cashflow',
          emphasis: { focus: 'series' },
          itemStyle: { color: categoryColorFn(cat.name) || undefined },
          data,
        };
      })
      .filter((seriesItem) => seriesItem.data.some((value) => value !== 0));

    breakoutChart.setOption(
      {
        color: PALETTE,
        animationDuration: 200,
        animationDurationUpdate: 200,
        grid: { left: 64, right: 24, top: 48, bottom: 52, containLabel: false },
        legend: {
          top: 6,
          type: 'scroll',
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          valueFormatter: (value) => formatCurrency(Math.abs(value)),
        },
        xAxis: {
          type: 'category',
          data: labels,
          axisTick: { alignWithLabel: true },
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            formatter: (value) => formatCurrency(Math.abs(value)),
          },
          splitLine: {
            lineStyle: { color: 'rgba(132, 91, 49, 0.16)' },
          },
        },
        series,
      },
      true
    );
  };

  return {
    renderTreemap,
    renderSankey,
    renderBreakout,
  };
};
