import { computed } from 'vue/dist/vue.esm-bundler.js';
import { formatCurrency } from '../utils/format.js';

export const TransactionsList = {
  name: 'TransactionsList',
  props: {
    model: { type: Object, required: true },
    filter: { type: String, default: null }, // 'expense' | 'income' | null (all)
    limit: { type: Number, default: 0 }, // 0 = no limit, use pagination
  },
  setup(props) {
    const filteredTxns = computed(() => {
      let txns = props.model.visibleTransactions || [];
      if (props.filter === 'expense') {
        txns = txns.filter(tx => tx.amount_cents < 0);
      } else if (props.filter === 'income') {
        txns = txns.filter(tx => tx.amount_cents >= 0);
      }
      if (props.limit > 0) {
        txns = txns.slice(0, props.limit);
      }
      return txns;
    });

    const filteredTotal = computed(() => {
      return filteredTxns.value.reduce((sum, tx) => sum + tx.amount_cents, 0);
    });

    const filteredCount = computed(() => filteredTxns.value.length);

    const showPagination = computed(() => !props.limit && props.model.filteredTransactionCount > 0);

    return {
      formatCurrency,
      filteredTxns,
      filteredTotal,
      filteredCount,
      showPagination,
    };
  },
  template: `
    <div class="panel transactions-panel">
      <div class="txn-header-bar">
        <div class="txn-header-main">
          <div class="txn-header">
            Transactions
            <span class="sub">{{ filteredCount }} transactions</span>
          </div>
        </div>
        <div class="txn-header-total">
          <div class="txn-total">
            <span class="txn-total-label">Total:</span>
            <span class="txn-total-value" :style="{ color: filteredTotal >= 0 ? 'var(--income-color)' : '#c1121f' }">
              {{ formatCurrency(filteredTotal) }}
            </span>
          </div>
        </div>
      </div>
      <div class="txn-table-wrap">
        <table>
          <thead>
            <tr>
              <th class="sortable-th" style="width:90px" @click="model.toggleTransactionSort('booking_date')">
                Date<span class="sort-marker">{{ model.transactionSortMarker('booking_date') }}</span>
              </th>
              <th class="sortable-th" style="width:100px" @click="model.toggleTransactionSort('account')">
                Account<span class="sort-marker">{{ model.transactionSortMarker('account') }}</span>
              </th>
              <th class="sortable-th" @click="model.toggleTransactionSort('description')">
                Description<span class="sort-marker">{{ model.transactionSortMarker('description') }}</span>
              </th>
              <th class="sortable-th" style="width:180px" @click="model.toggleTransactionSort('category')">
                Category<span class="sort-marker">{{ model.transactionSortMarker('category') }}</span>
              </th>
              <th class="sortable-th text-right" style="width:100px" @click="model.toggleTransactionSort('amount_cents')">
                Amount<span class="sort-marker">{{ model.transactionSortMarker('amount_cents') }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tx in filteredTxns" :key="tx.fp">
              <td>{{ tx.booking_date }}</td>
              <td>
                <button type="button" class="breadcrumb-link" @click="model.applyAccountFilter(tx.account_id)">
                  {{ tx.account }}{{ tx.subaccount ? '/' + tx.subaccount : '' }}
                </button>
              </td>
              <td class="desc-cell" style="font-size: 0.85rem;">{{ tx.raw_description || tx.description }}</td>
              <td>
                <span class="category-entry">
                  <span class="cat-dot" :style="{ background: model.categoryColor(tx.category) || 'var(--muted)' }"></span>
                  <button type="button" class="breadcrumb-link mono category-cell" @click="model.applyCategorySelection(tx.category)">
                    {{ tx.category }}
                  </button>
                </span>
              </td>
              <td class="text-right" :style="{ color: tx.amount_cents >= 0 ? 'var(--income-color)' : '#c1121f' }">
                {{ formatCurrency(tx.amount_cents) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="showPagination" class="txn-footer">
        <span class="txn-footer-summary">
          Showing {{ model.transactionRangeStart }}-{{ model.transactionRangeEnd }} of {{ model.filteredTransactionCount }}
        </span>
        <div class="pagination-controls">
          <button class="shortcut-btn" @click="model.goToTransactionPage(1)" :disabled="model.currentTransactionPage === 1">First</button>
          <button class="shortcut-btn" @click="model.goToPreviousTransactionPage()" :disabled="model.currentTransactionPage === 1">Prev</button>
          <button v-for="page in model.transactionPageButtons" :key="page" class="shortcut-btn"
            :class="{ active: model.currentTransactionPage === page }" @click="model.goToTransactionPage(page)">{{ page }}</button>
          <button class="shortcut-btn" @click="model.goToNextTransactionPage()" :disabled="model.currentTransactionPage === model.totalTransactionPages">Next</button>
          <button class="shortcut-btn" @click="model.goToTransactionPage(model.totalTransactionPages)" :disabled="model.currentTransactionPage === model.totalTransactionPages">Last</button>
        </div>
      </div>
    </div>
  `,
};
