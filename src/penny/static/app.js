const { createApp, ref, reactive, watch, onMounted, nextTick, computed } = Vue;

createApp({
  setup() {
    // ── State ────────────────────────────────────────────────────────
    const view = ref('report'); // Main navigation: import, accounts, transactions, classify, report
    const meta = reactive({ accounts: [], min_date: '', max_date: '' });
    const filters = reactive({
      from: '',
      to: '',
      accounts: [],
      neutralize: true,
    });
    const tab = ref('expense');
    const summary = ref(null);
    const tree = ref(null);
    const pivot = ref(null);
    const cashflow = ref(null);
    const breakout = ref(null);
    const breakoutGranularityMode = ref('auto');
    const breakoutShowIncome = ref(true);
    const breakoutShowExpenses = ref(true);
    const pivotDepth = ref('1');
    const transactions = ref(null);
    const selectedCategory = ref(null);
    const yearButtons = ref([]);
    const categoryColorMap = reactive({});
    const reportText = ref('');
    const copyLabel = ref('Copy to clipboard');
    const pivotCopyLabel = ref('MD');
    const transactionsCopyLabel = ref('MD');
    const searchQuery = ref('');
    const transactionListEl = ref(null);
    const visibleTransactionCount = ref(250);
    const transactionSort = reactive({ key: 'booking_date', direction: 'desc' });
    const monthRangeAnchor = ref(null);
    let searchTimer = null;
    const TRANSACTION_BATCH_SIZE = 250;

    // Chart refs
    const treemapEl = ref(null);
    const sankeyEl = ref(null);
    const breakoutEl = ref(null);
    let treemapChart = null;
    let sankeyChart = null;
    let breakoutChart = null;

    // Warm earthy palette derived from old report, auto-assigned by ECharts
    const PALETTE = [
      '#5d8a66', '#c67b47', '#7b68a6', '#4a90a4', '#d4a84b',
      '#8b7355', '#a35d6a', '#6b8e9f', '#9b7653', '#6a9a8a',
      '#b86b4c', '#7d8471', '#8c6d8a', '#6e7b8b', '#9c7a97',
      '#7aa37a', '#8b8378', '#5c7a6e', '#7a8b6e', '#9878a0',
    ];

    // ── Helpers ──────────────────────────────────────────────────────
    function fmt(cents) {
      if (cents == null) return '–';
      return (cents / 100).toLocaleString('de-DE', {
        style: 'currency', currency: 'EUR',
      });
    }

    function escapeMarkdownCell(value) {
      return String(value ?? '')
        .replace(/\|/g, '\\|')
        .replace(/\n/g, ' ')
        .trim();
    }

    function toMarkdownTable(headers, rows) {
      const head = `| ${headers.map(escapeMarkdownCell).join(' | ')} |`;
      const sep = `| ${headers.map(() => '---').join(' | ')} |`;
      const body = rows.map((row) => `| ${row.map(escapeMarkdownCell).join(' | ')} |`);
      return [head, sep, ...body].join('\n');
    }

    function setYear(year) {
      filters.from = `${year}-01-01`;
      filters.to = `${year}-12-31`;
      monthRangeAnchor.value = null;
    }

    function setAll() {
      filters.from = meta.min_date;
      filters.to = meta.max_date;
      monthRangeAnchor.value = null;
    }

    function toggleAccount(account) {
      const index = filters.accounts.indexOf(account);
      if (index === -1) {
        filters.accounts.push(account);
      } else {
        filters.accounts.splice(index, 1);
      }
    }

    const monthButtons = [
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

    const monthShortcutYear = computed(() => {
      if (!filters.from || !filters.to) return null;
      const fromYear = parseInt(filters.from.slice(0, 4), 10);
      const toYear = parseInt(filters.to.slice(0, 4), 10);
      return fromYear === toYear ? fromYear : null;
    });

    function daysInMonth(year, month) {
      return new Date(year, month, 0).getDate();
    }

    function setMonthRange(year, fromMonth, toMonth) {
      const startMonth = Math.min(fromMonth, toMonth);
      const endMonth = Math.max(fromMonth, toMonth);
      const fromMm = String(startMonth).padStart(2, '0');
      const toMm = String(endMonth).padStart(2, '0');
      const dd = String(daysInMonth(year, endMonth)).padStart(2, '0');
      filters.from = `${year}-${fromMm}-01`;
      filters.to = `${year}-${toMm}-${dd}`;
    }

    function selectedMonthRange() {
      const year = monthShortcutYear.value;
      if (year == null || !filters.from || !filters.to) return null;
      const fromMonth = parseInt(filters.from.slice(5, 7), 10);
      const toMonth = parseInt(filters.to.slice(5, 7), 10);
      const toDay = parseInt(filters.to.slice(8, 10), 10);
      if (filters.from.slice(8, 10) !== '01') return null;
      if (toDay !== daysInMonth(year, toMonth)) return null;
      return { year, fromMonth, toMonth };
    }

    function setMonth(event, month) {
      const year = monthShortcutYear.value;
      if (year == null) return;
      if (event?.shiftKey && monthRangeAnchor.value != null) {
        setMonthRange(year, monthRangeAnchor.value, month);
        return;
      }
      monthRangeAnchor.value = month;
      setMonthRange(year, month, month);
    }

    function setYearAllMonths() {
      if (monthShortcutYear.value == null) {
        setAll();
        return;
      }
      monthRangeAnchor.value = null;
      setYear(monthShortcutYear.value);
    }

    function isActiveMonth(month) {
      const range = selectedMonthRange();
      if (!range) return false;
      return range.fromMonth <= month && month <= range.toMonth;
    }

    function isActiveYear(year) {
      if (!filters.from || !filters.to) return false;
      return (
        parseInt(filters.from.slice(0, 4), 10) === year
        && parseInt(filters.to.slice(0, 4), 10) === year
      );
    }

    function isFullYearRange() {
      if (!filters.from || !filters.to) return false;
      const fromYear = parseInt(filters.from.slice(0, 4), 10);
      const toYear = parseInt(filters.to.slice(0, 4), 10);
      return (
        fromYear === toYear
        && filters.from === `${fromYear}-01-01`
        && filters.to === `${toYear}-12-31`
      );
    }

    function isFullMonthRange() {
      if (!filters.from || !filters.to) return false;
      const fromYear = parseInt(filters.from.slice(0, 4), 10);
      const toYear = parseInt(filters.to.slice(0, 4), 10);
      const fromMonth = parseInt(filters.from.slice(5, 7), 10);
      const toMonth = parseInt(filters.to.slice(5, 7), 10);
      const dd = String(daysInMonth(fromYear, fromMonth)).padStart(2, '0');
      return (
        fromYear === toYear
        && fromMonth === toMonth
        && filters.from === `${fromYear}-${String(fromMonth).padStart(2, '0')}-01`
        && filters.to === `${toYear}-${String(toMonth).padStart(2, '0')}-${dd}`
      );
    }

    const breakoutGranularity = computed(() => {
      if (breakoutGranularityMode.value !== 'auto') return breakoutGranularityMode.value;
      if (isFullYearRange()) return 'month';
      if (isFullMonthRange()) return 'week';
      return 'month';
    });

    function breakoutGranularityLabel(value) {
      return { month: 'Monthly', week: 'Weekly', day: 'Daily' }[value] || value;
    }

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

    function fmtCompactSigned(cents) {
      const sign = cents >= 0 ? '+' : '-';
      const eur = Math.abs(cents) / 100;
      let value = eur;
      let suffix = '';
      if (eur >= 1_000_000) {
        value = eur / 1_000_000;
        suffix = 'm';
      } else if (eur >= 1_000) {
        value = eur / 1_000;
        suffix = 'k';
      }
      const digits = value >= 10 || suffix === '' ? 0 : 1;
      const text = value.toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: digits,
      });
      return `${text}${suffix}${sign}`;
    }

    const TRANSFER_GRAY = '#c8c8c8';

    function categoryColor(cat) {
      if (!cat) return null;
      const l1 = cat.includes('/') ? cat.split('/')[0] : cat;
      if (l1 === 'transfer') return TRANSFER_GRAY;
      return categoryColorMap[l1] || null;
    }

    function ensureCategoryColors(categories) {
      categories.forEach((cat, i) => {
        if (categoryColorMap[cat]) return;
        categoryColorMap[cat] = cat === 'transfer'
          ? TRANSFER_GRAY
          : PALETTE[i % PALETTE.length];
      });
    }

    function selectedMatchesCategory(category) {
      if (!selectedCategory.value || !category) return false;
      return selectedCategory.value === category || selectedCategory.value.startsWith(`${category}/`);
    }

    const categoryBreadcrumbs = computed(() => {
      if (!selectedCategory.value) return [];
      const parts = selectedCategory.value.split('/').filter(Boolean);
      return parts.map((label, index) => ({
        label,
        path: parts.slice(0, index + 1).join('/'),
      }));
    });

    function queryString() {
      const p = new URLSearchParams();
      p.set('from', filters.from);
      p.set('to', filters.to);
      p.set('accounts', filters.accounts.join(','));
      p.set('neutralize', filters.neutralize);
      return p.toString();
    }

    async function fetchJson(path) {
      const resp = await fetch(`${path}${path.includes('?') ? '&' : '?'}${queryString()}`);
      return resp.json();
    }

    // ── Data fetching ────────────────────────────────────────────────
    async function loadSummary() {
      summary.value = await fetchJson('/api/summary');
    }

    async function loadTree() {
      const catParam = selectedCategory.value
        ? `&category=${encodeURIComponent(selectedCategory.value)}`
        : '';
      tree.value = await fetchJson(`/api/tree?tab=${tab.value}${catParam}`);
      // Build L1 → color map from tree order (matches ECharts auto-assignment)
      if (tree.value && tree.value.children) {
        ensureCategoryColors(tree.value.children.map(l1 => l1.name));
      }
      await nextTick();
      renderTreemap();
    }

    async function loadPivot() {
      const catParam = selectedCategory.value
        ? `&category=${encodeURIComponent(selectedCategory.value)}`
        : '';
      pivot.value = await fetchJson(`/api/pivot?tab=${tab.value}&depth=${pivotDepth.value}${catParam}`);
    }

    async function loadCashflow() {
      const catParam = selectedCategory.value
        ? `&category=${encodeURIComponent(selectedCategory.value)}`
        : '';
      cashflow.value = await fetchJson(`/api/cashflow?${catParam.slice(1)}`);
      await nextTick();
      renderSankey();
    }

    async function loadBreakout() {
      const catParam = selectedCategory.value
        ? `&category=${encodeURIComponent(selectedCategory.value)}`
        : '';
      breakout.value = await fetchJson(`/api/breakout?granularity=${breakoutGranularity.value}${catParam}`);
      ensureCategoryColors((breakout.value?.categories || []).map(cat => cat.name));
      await nextTick();
      renderBreakout();
    }

    async function loadReport() {
      const resp = await fetch(`/api/report?${queryString()}`);
      reportText.value = await resp.text();
    }

    async function copyReport() {
      try {
        await navigator.clipboard.writeText(reportText.value);
        copyLabel.value = 'Copied ✓';
        setTimeout(() => { copyLabel.value = 'Copy to clipboard'; }, 2000);
      } catch {
        copyLabel.value = 'Copy failed';
        setTimeout(() => { copyLabel.value = 'Copy to clipboard'; }, 2000);
      }
    }

    async function copyPivotTable() {
      if (!pivot.value) return;
      const markdown = toMarkdownTable(
        ['Category', 'Count', 'Share', 'Total', 'Weekly Avg', 'Monthly Avg', 'Yearly Avg'],
        pivot.value.categories.map((row) => [
          row.category,
          row.txn_count,
          `${Math.round(row.share * 100)}%`,
          fmt(row.total_cents),
          fmt(row.weekly_avg_cents),
          fmt(row.monthly_avg_cents),
          fmt(row.yearly_avg_cents),
        ]),
      );
      try {
        await navigator.clipboard.writeText(markdown);
        pivotCopyLabel.value = 'OK';
        setTimeout(() => { pivotCopyLabel.value = 'MD'; }, 2000);
      } catch {
        pivotCopyLabel.value = 'ERR';
        setTimeout(() => { pivotCopyLabel.value = 'MD'; }, 2000);
      }
    }

    async function copyTransactionsTable() {
      const markdown = toMarkdownTable(
        ['Date', 'Account', 'Description', 'Merchant', 'Category', 'Amount'],
        sortedTransactions.value.map((row) => [
          row.booking_date,
          row.account,
          row.description,
          row.merchant,
          row.category,
          fmt(row.amount_cents),
        ]),
      );
      try {
        await navigator.clipboard.writeText(markdown);
        transactionsCopyLabel.value = 'OK';
        setTimeout(() => { transactionsCopyLabel.value = 'MD'; }, 2000);
      } catch {
        transactionsCopyLabel.value = 'ERR';
        setTimeout(() => { transactionsCopyLabel.value = 'MD'; }, 2000);
      }
    }

    async function loadTransactions() {
      const catParam = selectedCategory.value
        ? `&category=${encodeURIComponent(selectedCategory.value)}`
        : '';
      const tabParam = (tab.value === 'cashflow' || tab.value === 'breakout')
        ? ''
        : `&tab=${tab.value}`;
      const qParam = searchQuery.value
        ? `&q=${encodeURIComponent(searchQuery.value)}`
        : '';
      transactions.value = await fetchJson(`/api/transactions?${tabParam}${catParam}${qParam}`);
      resetTransactionWindow();
    }

    async function applyCategorySelection(category) {
      selectedCategory.value = category;
      searchQuery.value = '';
      if (tab.value === 'expense' || tab.value === 'income') {
        await Promise.all([loadTree(), loadPivot(), loadTransactions()]);
        return;
      }
      if (tab.value === 'cashflow') {
        await Promise.all([loadCashflow(), loadTransactions()]);
        return;
      }
      if (tab.value === 'breakout') {
        await Promise.all([loadBreakout(), loadTransactions()]);
        return;
      }
      await loadTransactions();
    }

    function clearSelection() {
      applyCategorySelection(null);
    }

    function compareValues(a, b) {
      if (a == null && b == null) return 0;
      if (a == null) return 1;
      if (b == null) return -1;
      if (typeof a === 'number' && typeof b === 'number') return a - b;
      return String(a).localeCompare(String(b), undefined, {
        numeric: true,
        sensitivity: 'base',
      });
    }

    const sortedTransactions = computed(() => {
      const rows = [...(transactions.value?.transactions || [])];
      const { key, direction } = transactionSort;
      const factor = direction === 'asc' ? 1 : -1;
      rows.sort((left, right) => {
        const primary = compareValues(left[key], right[key]) * factor;
        if (primary !== 0) return primary;
        return compareValues(left.fp, right.fp);
      });
      return rows;
    });

    const visibleTransactions = computed(() => {
      const rows = sortedTransactions.value;
      return rows.slice(0, visibleTransactionCount.value);
    });

    function toggleTransactionSort(key) {
      if (transactionSort.key === key) {
        transactionSort.direction = transactionSort.direction === 'asc' ? 'desc' : 'asc';
        return;
      }
      transactionSort.key = key;
      transactionSort.direction = key === 'amount_cents' ? 'desc' : 'asc';
    }

    function transactionSortMarker(key) {
      if (transactionSort.key !== key) return '';
      return transactionSort.direction === 'asc' ? '↑' : '↓';
    }

    function resetTransactionWindow() {
      visibleTransactionCount.value = TRANSACTION_BATCH_SIZE;
      nextTick(() => {
        if (transactionListEl.value) transactionListEl.value.scrollTop = 0;
      });
    }

    function growTransactionWindow() {
      const rows = transactions.value?.transactions || [];
      if (visibleTransactionCount.value >= rows.length) return;
      visibleTransactionCount.value = Math.min(
        rows.length,
        visibleTransactionCount.value + TRANSACTION_BATCH_SIZE,
      );
    }

    function onTransactionScroll(event) {
      const el = event.target;
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 160) {
        growTransactionWindow();
      }
    }

    async function loadAll() {
      if (!filters.from || !filters.to) return;
      const loads = [loadSummary()];
      if (tab.value === 'cashflow') {
        loads.push(loadCashflow());
        loads.push(loadTransactions());
      } else if (tab.value === 'breakout') {
        loads.push(loadBreakout());
        loads.push(loadTransactions());
      } else if (tab.value === 'report') {
        loads.push(loadReport());
      } else {
        loads.push(loadTree());
        loads.push(loadPivot());
        loads.push(loadTransactions());
      }
      await Promise.all(loads);
    }

    // ── Charts ───────────────────────────────────────────────────────
    function treeToECharts(node) {
      if (!node || !node.children) return [];
      return node.children.map((l1, i) => {
        const color = l1.name === 'transfer' ? TRANSFER_GRAY : undefined;
        return {
          name: l1.name,
          value: l1.value,
          itemStyle: color ? { color } : undefined,
          children: (l1.children || []).map(l2 => ({
            name: l2.name === '(uncategorized)' ? l1.name : `${l1.name}/${l2.name}`,
            value: l2.value,
            children: (l2.children || []).map(m => ({
              name: m.name,
              value: m.value,
            })),
          })),
        };
      });
    }

    function renderTreemap() {
      if (!treemapEl.value || !tree.value) return;
      // v-if may have destroyed the DOM element; always re-check
      if (treemapChart && treemapChart.getDom() !== treemapEl.value) {
        treemapChart.dispose();
        treemapChart = null;
      }
      if (!treemapChart) {
        treemapChart = echarts.init(treemapEl.value);
        treemapChart.on('click', (params) => {
          if (params.treePathInfo && params.treePathInfo.length >= 2) {
            // L2 nodes already have full path names (e.g. "tax/refund"),
            // so use the deepest node's name directly
            const deepest = params.treePathInfo[params.treePathInfo.length - 1].name;
            applyCategorySelection(deepest);
          }
        });
      }
      treemapChart.setOption({
        color: PALETTE,
        tooltip: {
          formatter: (p) => `${p.name}<br/>${fmt(p.value)}`,
        },
        animationDurationUpdate: 200,
        series: [{
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
        }],
      }, true);
    }

    function renderSankey() {
      if (!sankeyEl.value || !cashflow.value) return;
      if (sankeyChart && sankeyChart.getDom() !== sankeyEl.value) {
        sankeyChart.dispose();
        sankeyChart = null;
      }
      if (!sankeyChart) {
        sankeyChart = echarts.init(sankeyEl.value);
        sankeyChart.on('click', (params) => {
          if (params.data && params.data.name && params.data.name !== 'Budget') {
            // Strip "(in)"/"(out)" suffix from disambiguated names
            const raw = params.data.name.replace(/ \((in|out)\)$/, '');
            applyCategorySelection(raw);
          }
        });
      }
      // Filter out tiny links for readability (< 1% of total expense)
      const minValue = cashflow.value.total_expense * 0.01;
      const links = cashflow.value.links.filter(l => l.value >= minValue);
      const nodeNames = new Set();
      links.forEach(l => { nodeNames.add(l.source); nodeNames.add(l.target); });
      const nodes = [...nodeNames].map(n => ({ name: n }));

      sankeyChart.setOption({
        color: PALETTE,
        tooltip: {
          formatter: (p) => p.data.source
            ? `${p.data.source} → ${p.data.target}<br/>${fmt(p.data.value)}`
            : `${p.data.name}`,
        },
        series: [{
          type: 'sankey',
          data: nodes,
          links: links,
          emphasis: { focus: 'adjacency' },
          label: { show: true, fontSize: 11 },
          lineStyle: { color: 'gradient', curveness: 0.5 },
          layoutIterations: 32,
        }],
      }, true);
    }

    function renderBreakout() {
      if (!breakoutEl.value || !breakout.value) return;
      if (breakoutChart && breakoutChart.getDom() !== breakoutEl.value) {
        breakoutChart.dispose();
        breakoutChart = null;
      }
      if (!breakoutChart) {
        breakoutChart = echarts.init(breakoutEl.value);
        breakoutChart.on('click', (params) => {
          if (!params.seriesName) return;
          applyCategorySelection(params.seriesName);
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
            itemStyle: { color: categoryColor(cat.name) || undefined },
            data,
          };
        })
        .filter((seriesItem) => seriesItem.data.some((value) => value !== 0));

      breakoutChart.setOption({
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
          valueFormatter: (value) => fmt(Math.abs(value)),
        },
        xAxis: {
          type: 'category',
          data: labels,
          axisTick: { alignWithLabel: true },
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            formatter: (value) => fmt(Math.abs(value)),
          },
          splitLine: {
            lineStyle: { color: 'rgba(132, 91, 49, 0.16)' },
          },
        },
        series,
      }, true);
    }

    // ── Watchers ─────────────────────────────────────────────────────
    watch(
      () => [filters.from, filters.to, filters.accounts.join(','), filters.neutralize],
      () => { loadAll(); },
    );

    watch(tab, () => {
      if (tab.value === 'cashflow') {
        loadCashflow();
        loadTransactions();
      } else if (tab.value === 'breakout') {
        loadBreakout();
        loadTransactions();
      } else if (tab.value === 'report') {
        loadReport();
      } else {
        loadTree();
        loadPivot();
        loadTransactions();
      }
    });

    watch(searchQuery, () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => loadTransactions(), 250);
    });

    watch(pivotDepth, () => {
      if (tab.value === 'expense' || tab.value === 'income') loadPivot();
    });

    watch(breakoutGranularityMode, () => {
      if (tab.value === 'breakout') loadBreakout();
    });

    watch([breakoutShowIncome, breakoutShowExpenses], () => {
      if (tab.value === 'breakout') renderBreakout();
    });

    // ── Init ─────────────────────────────────────────────────────────
    onMounted(async () => {
      const m = await (await fetch('/api/meta')).json();
      meta.accounts = m.accounts;
      meta.min_date = m.min_date;
      meta.max_date = m.max_date;

      // Compute year shortcut buttons from data range
      const minY = parseInt(m.min_date.slice(0, 4));
      const maxY = parseInt(m.max_date.slice(0, 4));
      const yrs = [];
      for (let y = minY; y <= maxY; y++) yrs.push(y);
      yearButtons.value = yrs;

      // Default to last full year
      const currentYear = new Date().getFullYear();
      const lastFullYear = currentYear - 1;
      filters.from = `${lastFullYear}-01-01`;
      filters.to = `${lastFullYear}-12-31`;
      filters.accounts = [...m.accounts];
      filters.neutralize = true;
    });

    // ── Expose ───────────────────────────────────────────────────────
    return {
      view, meta, filters, tab, summary, tree, pivot, cashflow, breakout, transactions,
      selectedCategory, treemapEl, sankeyEl, breakoutEl, fmt,
      yearButtons, setYear, setAll, toggleAccount, clearSelection, categoryColor, isActiveYear,
      monthButtons, monthShortcutYear, setMonth, setYearAllMonths, isActiveMonth,
      breakoutGranularityMode, breakoutGranularity, breakoutGranularityLabel,
      breakoutNet, breakoutNetByPeriod, fmtCompactSigned,
      breakoutShowIncome, breakoutShowExpenses,
      pivotDepth, selectedMatchesCategory, categoryBreadcrumbs,
      applyCategorySelection,
      transactionSort, toggleTransactionSort, transactionSortMarker,
      reportText, copyReport, copyLabel, searchQuery,
      pivotCopyLabel, transactionsCopyLabel, copyPivotTable, copyTransactionsTable,
      transactionListEl, visibleTransactions, visibleTransactionCount,
      onTransactionScroll, growTransactionWindow,
    };
  },
}).mount('#app');
