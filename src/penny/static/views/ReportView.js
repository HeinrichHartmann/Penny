import { SelectorHeader } from '../components/SelectorHeader.js';
import { TransactionsList } from './TransactionsList.js';
import { breakoutGranularityLabel } from '../utils/date.js';
import { formatCompactSigned, formatCurrency } from '../utils/format.js';

export const ReportView = {
  name: 'ReportView',
  components: {
    SelectorHeader,
    TransactionsList,
  },
  props: {
    model: { type: Object, required: true },
    transactionsModel: { type: Object, required: false },
  },
  setup() {
    return {
      breakoutGranularityLabel,
      formatCompactSigned,
      formatCurrency,
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
          <button v-for="t in ['expense', 'income', 'cashflow', 'breakout']" :key="t"
            @click="model.setTab(t)" :data-tab="t"
            :class="['tab-btn', model.tab === t ? 'active' : '']">
            {{ {expense:'Expense', income:'Income', cashflow:'Cash Flow', breakout:'Breakout'}[t] }}
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
          <div class="breakout-header">
            <div class="txn-header" style="margin:0;">
              {{ breakoutGranularityLabel(model.breakoutGranularity) }} Breakout
              <span class="sub" v-if="model.breakout">
                - inflows {{ formatCurrency(model.breakout.income_total) }}, outflows {{ formatCurrency(model.breakout.expense_total) }}
              </span>
            </div>
            <div class="breakout-middle">
              <div class="check-group">
                <label>
                  <input type="checkbox" :checked="model.breakoutShowIncome" @change="model.setBreakoutShowIncome($event.target.checked)">
                  Income
                </label>
                <label>
                  <input type="checkbox" :checked="model.breakoutShowExpenses" @change="model.setBreakoutShowExpenses($event.target.checked)">
                  Expenses
                </label>
              </div>
            </div>
            <div class="btn-group wrap">
              <button @click="model.setBreakoutGranularityMode('auto')"
                :class="['shortcut-btn', model.breakoutGranularityMode === 'auto' ? 'active' : '']">
                Auto
              </button>
              <button @click="model.setBreakoutGranularityMode('month')"
                :class="['shortcut-btn', model.breakoutGranularityMode === 'month' ? 'active' : '']">
                Month
              </button>
              <button @click="model.setBreakoutGranularityMode('week')"
                :class="['shortcut-btn', model.breakoutGranularityMode === 'week' ? 'active' : '']">
                Week
              </button>
              <button @click="model.setBreakoutGranularityMode('day')"
                :class="['shortcut-btn', model.breakoutGranularityMode === 'day' ? 'active' : '']">
                Day
              </button>
            </div>
          </div>
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

        <div v-if="model.tab === 'report'" class="panel" style="margin-bottom:20px; border-radius:0 6px 6px 6px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
            <span class="txn-header" style="margin:0">Text Report</span>
            <button class="copy-btn" @click="model.copyReport">{{ model.copyLabel }}</button>
          </div>
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
