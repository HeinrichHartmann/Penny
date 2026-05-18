import { ref } from 'vue/dist/vue.esm-bundler.js';
import { BreakoutSelector } from '../components/BreakoutSelector.js';
import { SelectorHeader } from '../components/SelectorHeader.js';
import { TransactionsList } from './TransactionsList.js';
import { formatCompactSigned, formatCurrency } from '../utils/format.js';

// ── Activity heatmap helpers ──────────────────────────────────────────────────

function buildYearGrid(year, daily, fromDate, toDate) {
  const jan1 = new Date(year, 0, 1);
  // GitHub starts week on Sunday; find the Sunday on or before Jan 1
  const startOffset = jan1.getDay(); // 0=Sun
  const gridStart = new Date(jan1);
  gridStart.setDate(gridStart.getDate() - startOffset);

  const cells = [];
  const d = new Date(gridStart);
  for (let col = 0; col < 53; col++) {
    for (let row = 0; row < 7; row++) {
      const iso = d.toISOString().slice(0, 10);
      const inYear = d.getFullYear() === year;
      const inRange = fromDate && toDate ? iso >= fromDate && iso <= toDate : inYear;
      const amount = daily ? (daily[iso] || 0) : 0;
      cells.push({ iso, inYear, inRange, amount, col, row });
      d.setDate(d.getDate() + 1);
    }
  }
  return cells;
}

// Log-scale color levels: 0=none, 1=<€5, 2=<€50, 3=<€500, 4=<€5k, 5=€5k+
// YlOrRd sequential for expenses, Greens sequential for income
const EXPENSE_COLORS = ['var(--surface)', '#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026'];
const INCOME_COLORS  = ['var(--surface)', '#edf8e9', '#bae4b3', '#74c476', '#31a354', '#006d2c'];

function activityLevel(amountCents) {
  const euros = amountCents / 100;
  if (euros === 0)     return 0;
  if (euros < 5)       return 1;
  if (euros < 50)      return 2;
  if (euros < 500)     return 3;
  if (euros < 5000)    return 4;
  return 5;
}

function activityColor(amountCents, inRange, inYear, type) {
  if (!inYear) return 'transparent';
  if (!inRange) return 'var(--border)';
  const level = activityLevel(amountCents);
  return type === 'income' ? INCOME_COLORS[level] : EXPENSE_COLORS[level];
}

const ACTIVITY_LEGEND = [
  { label: '€0',    level: 0 },
  { label: '<€5',   level: 1 },
  { label: '<€50',  level: 2 },
  { label: '<€500', level: 3 },
  { label: '<€5k',  level: 4 },
  { label: '€5k+',  level: 5 },
];

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const DAY_LABELS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function monthLabelCols(year) {
  // Return [{label, col}] for each month, placed at the week-column where the month starts
  const labels = [];
  for (let m = 0; m < 12; m++) {
    const firstDay = new Date(year, m, 1);
    const jan1 = new Date(year, 0, 1);
    const startOffset = jan1.getDay();
    const dayOfYear = Math.floor((firstDay - new Date(year, 0, 0)) / 86400000);
    const col = Math.floor((dayOfYear - 1 + startOffset) / 7);
    labels.push({ label: MONTH_LABELS[m], col });
  }
  return labels;
}

export const ReportView = {
  name: 'ReportView',
  components: {
    BreakoutSelector,
    SelectorHeader,
    TransactionsList,
  },
  props: {
    model: { type: Object, required: true },
    transactionsModel: { type: Object, required: false },
  },
  setup() {
    const heatmapRowSort = ref('alpha'); // 'alpha' | 'total'
    return {
      formatCompactSigned,
      formatCurrency,
      buildYearGrid,
      activityColor,
      activityLevel,
      monthLabelCols,
      DAY_LABELS,
      EXPENSE_COLORS,
      INCOME_COLORS,
      ACTIVITY_LEGEND,
      heatmapRowSort,
    };
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Report</h2>

      <selector-header
        :state="model.selectorState"
        :actions="model.selectorActions"
      ></selector-header>

      <div class="summary-grid" v-if="model.summary">
        <div class="panel summary-card">
          <div class="label">Expenses</div>
          <div class="value expense-color">{{ formatCurrency(model.summary.expense.total_cents) }}</div>
          <div class="sub">{{ model.summary.expense.count }} transactions</div>
        </div>
        <div class="panel summary-card">
          <div class="label">Income</div>
          <div class="value income-color">{{ formatCurrency(model.summary.income.total_cents) }}</div>
          <div class="sub">{{ model.summary.income.count }} transactions</div>
        </div>
        <div class="panel summary-card">
          <div class="label">Net Flow</div>
          <div class="value" :class="model.summary.net_flow >= 0 ? 'income-color' : 'expense-color'">
            {{ formatCurrency(model.summary.net_flow) }}
          </div>
        </div>
      </div>

      <div class="tabs">
        <div class="tab-group">
          <button v-for="t in ['expense', 'income', 'cashflow', 'breakout', 'activity', 'heatmap']" :key="t"
            @click="model.setTab(t)" :data-tab="t"
            :class="['tab-btn', model.tab === t ? 'active' : '']">
            {{ {expense:'Expense', income:'Income', cashflow:'Cash Flow', breakout:'Breakout', activity:'Activity', heatmap:'Activity Breakout'}[t] }}
          </button>
        </div>
        <div class="tab-group">
          <button @click="model.setTab('report')" data-tab="report"
            :class="['tab-btn', model.tab === 'report' ? 'active' : '']">
            Report
          </button>
        </div>
      </div>

      <div class="tab-content">
        <div v-if="model.tab === 'expense' || model.tab === 'income'" class="panel" style="margin-bottom:20px; border-radius:0 6px 6px 6px;">
          <div :ref="model.setTreemapEl" style="width:100%; height:500px;"></div>
        </div>

        <div v-if="model.tab === 'breakout'" class="panel" style="margin-bottom:20px; border-radius:0 6px 6px 6px;">
          <breakout-selector
            :state="{ granularityMode: model.breakoutGranularityMode, showIncome: model.breakoutShowIncome, showExpenses: model.breakoutShowExpenses }"
            :actions="{ setGranularityMode: model.setBreakoutGranularityMode, setShowIncome: model.setBreakoutShowIncome, setShowExpenses: model.setBreakoutShowExpenses }"
          >
            <span v-if="model.breakout" class="sub" style="margin-right:auto;">
              inflows {{ formatCurrency(model.breakout.income_total) }}, outflows {{ formatCurrency(model.breakout.expense_total) }}
            </span>
          </breakout-selector>
          <div :ref="model.setBreakoutEl" style="width:100%; height:520px;"></div>
          <div v-if="model.breakout && model.breakoutNetByPeriod.length" class="breakout-net-caption">Balance</div>
          <div v-if="model.breakout && model.breakoutNetByPeriod.length" class="breakout-net-row"
            :style="{ gridTemplateColumns: \`repeat(\${model.breakoutNetByPeriod.length}, minmax(0, 1fr))\` }">
            <div v-for="(net, index) in model.breakoutNetByPeriod" :key="\`\${model.breakout.periods[index]}-net\`"
              class="breakout-net-cell" :style="{ color: net < 0 ? '#c1121f' : 'var(--ink)' }">
              {{ formatCompactSigned(net) }}
            </div>
          </div>
          <div class="breakout-net" v-if="model.breakoutNet !== null">
            Net:
            <span :style="{ color: model.breakoutNet < 0 ? '#c1121f' : 'var(--ink)' }">
              {{ formatCurrency(model.breakoutNet) }}
            </span>
          </div>
        </div>

        <div v-if="model.tab === 'cashflow'" class="panel" style="margin-bottom:20px; border-radius:0 6px 6px 6px;">
          <div :ref="model.setSankeyEl" style="width:100%; height:500px;"></div>
        </div>

        <div v-if="model.tab === 'activity' && model.activity" style="margin-bottom:20px;">
          <template v-for="type in ['expense', 'income']" :key="type">
            <div class="panel" style="margin-bottom:16px; border-radius:6px; overflow-x:auto;">
              <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;">
                <div class="txn-header" style="margin:0; text-transform:capitalize;">{{ type }}</div>
                <div style="display:flex; align-items:center; gap:6px; font-size:0.7rem; color:var(--muted);">
                  <span>Less</span>
                  <div v-for="item in ACTIVITY_LEGEND" :key="item.label" style="display:flex; align-items:center; gap:2px;">
                    <div :style="{
                      width:'11px', height:'11px', borderRadius:'2px',
                      background: type === 'income' ? INCOME_COLORS[item.level] : EXPENSE_COLORS[item.level],
                      outline: '1px solid rgba(27,31,35,0.06)',
                      outlineOffset: '-1px',
                    }"></div>
                    <span>{{ item.label }}</span>
                  </div>
                  <span>More</span>
                </div>
              </div>
              <template v-for="year in (() => {
                const from = model.activity.from; const to = model.activity.to;
                const y1 = from ? parseInt(from.slice(0,4)) : new Date().getFullYear();
                const y2 = to   ? parseInt(to.slice(0,4))   : new Date().getFullYear();
                const ys = []; for (let y = y1; y <= y2; y++) ys.push(y); return ys;
              })()" :key="year">
                <div style="font-size:0.85rem; color:var(--muted); margin-bottom:4px;">{{ year }}</div>
                <div style="position:relative; margin-bottom:20px;">
                  <!-- Month labels -->
                  <div style="display:grid; grid-template-columns:28px repeat(53,11px); gap:2px; margin-bottom:2px;">
                    <div></div>
                    <template v-for="col in 53" :key="col">
                      <div :style="{ fontSize:'0.7rem', color:'var(--muted)', whiteSpace:'nowrap' }">
                        {{ (() => { const m = monthLabelCols(year).find(m => m.col === col - 1); return m ? m.label : ''; })() }}
                      </div>
                    </template>
                  </div>
                  <!-- Grid -->
                  <div style="display:flex; gap:0;">
                    <!-- Day labels -->
                    <div style="display:grid; grid-template-rows:repeat(7,11px); gap:2px; margin-right:4px; width:28px;">
                      <div v-for="(d,i) in DAY_LABELS" :key="d"
                        :style="{ fontSize:'0.65rem', color: i%2===1 ? 'var(--muted)' : 'transparent', lineHeight:'11px' }">
                        {{ d }}
                      </div>
                    </div>
                    <!-- Week columns — one CSS grid per week -->
                    <div style="display:flex; gap:2px;">
                      <template v-for="(cells, col) in (() => {
                        const grid = buildYearGrid(year, type === 'income' ? model.activity.daily_income : model.activity.daily_expense, model.activity.from, model.activity.to);
                        const cols = [];
                        for (let c = 0; c < 53; c++) cols.push(grid.filter(x => x.col === c));
                        return cols;
                      })()" :key="col">
                        <div style="display:grid; grid-template-rows:repeat(7,11px); gap:2px;">
                          <div v-for="cell in cells" :key="cell.iso"
                            :title="cell.iso + (cell.amount ? ': €' + (cell.amount/100).toFixed(2) : '')"
                            :style="{
                              width: '11px', height: '11px', borderRadius: '2px',
                              background: activityColor(cell.amount, cell.inRange, cell.inYear, type),
                              outline: cell.inYear ? '1px solid rgba(27,31,35,0.06)' : 'none',
                              outlineOffset: '-1px',
                            }">
                          </div>
                        </div>
                      </template>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </template>
        </div>
        <div v-else-if="model.tab === 'activity' && !model.activity" class="panel" style="margin-bottom:20px;">
          Loading...
        </div>

        <div v-if="model.tab === 'heatmap'" class="panel" style="margin-bottom:20px; border-radius:0 6px 6px 6px;">
          <breakout-selector
            :state="{ granularityMode: model.reportGranularityMode, showIncome: model.reportShowIncome, showExpenses: model.reportShowExpenses }"
            :actions="{ setGranularityMode: model.setReportGranularityMode, setShowIncome: model.setReportShowIncome, setShowExpenses: model.setReportShowExpenses }"
          >
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="sub">Depth</span>
              <div class="btn-group">
                <button v-for="d in ['1','2','*']" :key="d"
                  @click="model.setReportDepth(d)"
                  :class="['shortcut-btn', model.reportDepth === d ? 'active' : '']">
                  {{ d }}
                </button>
              </div>
            </div>
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="sub">Sort</span>
              <div class="btn-group">
                <button @click="heatmapRowSort = 'alpha'"
                  :class="['shortcut-btn', heatmapRowSort === 'alpha' ? 'active' : '']">A-Z</button>
                <button @click="heatmapRowSort = 'total'"
                  :class="['shortcut-btn', heatmapRowSort === 'total' ? 'active' : '']">Total</button>
              </div>
            </div>
          </breakout-selector>
          <div v-if="!model.heatmap" style="padding:20px; color:var(--muted);">Loading...</div>
          <template v-else>
            <template v-for="type in (() => {
              const t = [];
              if (model.reportShowExpenses) t.push('expense');
              if (model.reportShowIncome) t.push('income');
              return t;
            })()" :key="type">
              <div style="margin-bottom:24px;">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                  <div class="txn-header" style="margin:0; text-transform:capitalize;">{{ type === 'expense' ? 'Expenses' : 'Income' }}</div>
                  <div style="display:flex; align-items:center; gap:6px; font-size:0.7rem; color:var(--muted);">
                    <span>Less</span>
                    <div v-for="item in ACTIVITY_LEGEND" :key="item.label" style="display:flex; align-items:center; gap:2px;">
                      <div :style="{
                        width:'11px', height:'11px', borderRadius:'2px',
                        background: type === 'income' ? INCOME_COLORS[item.level] : EXPENSE_COLORS[item.level],
                        outline: '1px solid rgba(27,31,35,0.06)',
                        outlineOffset: '-1px',
                      }"></div>
                      <span>{{ item.label }}</span>
                    </div>
                    <span>More</span>
                  </div>
                </div>
                <div style="overflow-x:auto;">
                  <div style="display:grid; gap:2px;"
                    :style="{ gridTemplateColumns: '160px repeat(' + (model.heatmap[type] ? model.heatmap.periods.length : 0) + ', 13px)' }">
                    <!-- Header row -->
                    <div></div>
                    <div v-for="(label, i) in model.heatmap.labels" :key="i"
                      style="width:13px; font-size:0.65rem; color:var(--muted); writing-mode:vertical-lr; transform:rotate(180deg); padding-bottom:4px; white-space:nowrap; text-align:right; height:60px;">
                      {{ label }}
                    </div>
                    <!-- Data rows -->
                    <template v-for="cat in (() => {
                      const cats = model.heatmap[type] ? [...model.heatmap[type].categories] : [];
                      if (heatmapRowSort === 'total') cats.sort((a, b) => b.values.reduce((s,v)=>s+v,0) - a.values.reduce((s,v)=>s+v,0));
                      return cats;
                    })()" :key="cat.name">
                      <div style="width:160px; font-size:0.78rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding-right:8px; line-height:13px; height:13px; display:flex; align-items:center;">
                        <span class="cat-dot" :style="{ background: model.categoryColor(cat.name) || 'var(--muted)' }"></span>
                        {{ cat.name }}
                      </div>
                      <div v-for="(period, pi) in model.heatmap.periods" :key="period"
                        :title="cat.name + ' / ' + model.heatmap.labels[pi] + ': ' + formatCurrency(cat.values[pi] || 0)"
                        :style="{
                          width: '13px',
                          height: '13px',
                          borderRadius: '2px',
                          outline: '1px solid rgba(27,31,35,0.06)',
                          outlineOffset: '-1px',
                          background: (type === 'income' ? INCOME_COLORS : EXPENSE_COLORS)[activityLevel(cat.values[pi] || 0)],
                        }">
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </template>
          </template>
        </div>

        <div v-if="model.tab === 'report'" class="panel" style="margin-bottom:20px; border-radius:0 6px 6px 6px;">
          <breakout-selector
            :state="{ granularityMode: model.reportGranularityMode, showIncome: model.reportShowIncome, showExpenses: model.reportShowExpenses }"
            :actions="{ setGranularityMode: model.setReportGranularityMode, setShowIncome: model.setReportShowIncome, setShowExpenses: model.setReportShowExpenses }"
          >
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="sub">Depth</span>
              <div class="btn-group">
                <button v-for="d in ['1','2','*']" :key="d"
                  @click="model.setReportDepth(d)"
                  :class="['shortcut-btn', model.reportDepth === d ? 'active' : '']">
                  {{ d }}
                </button>
              </div>
            </div>
            <template #right>
              <button class="copy-btn" @click="model.copyReport">{{ model.copyLabel }}</button>
            </template>
          </breakout-selector>
          <pre class="report-text">{{ model.reportText || 'Loading...' }}</pre>
        </div>
      </div>

      <div v-if="(model.tab === 'expense' || model.tab === 'income') && model.pivot" class="panel" style="margin-top:20px;">
        <div class="txn-header-bar">
          <div style="display:flex; gap:10px; align-items:center; flex-wrap:wrap;">
            <div class="txn-header">
              Pivot Table
              <span class="sub">
                - {{ model.pivot.count }} rows, {{ formatCurrency(model.pivot.total_cents) }}
              </span>
            </div>
            <button class="shortcut-btn icon-btn" @click="model.copyPivotTable" title="Copy as Markdown">
              {{ model.pivotCopyLabel }}
            </button>
          </div>
          <div class="btn-group wrap">
            <button @click="model.setPivotDepth('1')"
              :class="['shortcut-btn', model.pivotDepth === '1' ? 'active' : '']">
              1
            </button>
            <button @click="model.setPivotDepth('2')"
              :class="['shortcut-btn', model.pivotDepth === '2' ? 'active' : '']">
              2
            </button>
            <button @click="model.setPivotDepth('*')"
              :class="['shortcut-btn', model.pivotDepth === '*' ? 'active' : '']">
              *
            </button>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Category
                <span class="sub" style="margin-left:6px;">Depth {{ model.pivotDepth }}</span>
              </th>
              <th style="width:90px">Count</th>
              <th style="width:90px">Share</th>
              <th class="text-right" style="width:120px">Total</th>
              <th class="text-right" style="width:120px">Weekly Avg</th>
              <th class="text-right" style="width:120px">Monthly Avg</th>
              <th class="text-right" style="width:120px">Yearly Avg</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in model.pivot.categories" :key="row.category"
              @click="model.applyCategorySelection(row.category)"
              :class="['pivot-row', model.selectedMatchesCategory(row.category) ? 'active' : '']">
              <td>
                <span class="cat-dot" :style="{ background: model.categoryColor(row.category) || 'var(--muted)' }"></span>
                <span class="mono">{{ row.category }}</span>
              </td>
              <td>{{ row.txn_count }}</td>
              <td class="share-cell">{{ Math.round(row.share * 100) }}%</td>
              <td class="text-right">{{ formatCurrency(row.total_cents) }}</td>
              <td class="text-right">{{ formatCurrency(row.weekly_avg_cents) }}</td>
              <td class="text-right">{{ formatCurrency(row.monthly_avg_cents) }}</td>
              <td class="text-right">{{ formatCurrency(row.yearly_avg_cents) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <transactions-list
        v-if="transactionsModel && (model.tab === 'expense' || model.tab === 'income')"
        :model="transactionsModel"
        :filter="model.tab"
        :limit="20"
        style="margin-top: 20px;"
      ></transactions-list>
    </div>
  `,
};
