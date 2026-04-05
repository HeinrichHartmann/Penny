import { onMounted } from 'vue/dist/vue.esm-bundler.js';

import { SelectorHeader } from '../components/SelectorHeader.js';
import { formatCurrency } from '../utils/format.js';

export const TransactionsView = {
  name: 'TransactionsView',
  components: {
    SelectorHeader,
  },
  props: {
    model: { type: Object, required: true },
  },
  setup(props) {
    onMounted(async () => {
      await props.model.loadTransactions();
    });

    return {
      formatCurrency,
    };
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Transactions</h2>

      <selector-header
        :state="model.selectorState"
        :actions="model.selectorActions"
      ></selector-header>

      <div class="panel transactions-panel">
        <div class="txn-header-bar">
          <div class="txn-header-main">
            <div class="txn-header">
              Transactions
              <span class="sub" v-if="model.transactions">{{ model.transactions.count }} transactions</span>
            </div>
          </div>
          <div class="txn-header-total">
            <div v-if="model.transactions" class="txn-total">
              <span class="txn-total-label">Total:</span>
              <span
                class="txn-total-value"
                :style="{ color: model.transactions.total_cents >= 0 ? 'var(--income-color)' : '#c1121f' }"
              >
                {{ formatCurrency(model.transactions.total_cents) }}
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
              <tr v-for="tx in model.visibleTransactions" :key="tx.fp">
                <td>{{ tx.booking_date }}</td>
                <td>
                  <button
                    type="button"
                    class="breadcrumb-link"
                    @click="model.applyAccountFilter(tx.account_id)"
                  >
                    {{ tx.account }}
                  </button>
                </td>
                <td class="desc-cell" style="font-size: 0.85rem;">{{ tx.raw_description || tx.description }}</td>
                <td>
                  <span class="category-entry">
                    <span class="cat-dot" :style="{ background: model.categoryColor(tx.category) || 'var(--muted)' }"></span>
                    <button
                      type="button"
                      class="breadcrumb-link mono category-cell"
                      @click="model.applyCategorySelection(tx.category)"
                    >
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
        <div v-if="model.transactions" class="txn-footer">
          <span class="txn-footer-summary">
            Showing {{ model.transactionRangeStart }}-{{ model.transactionRangeEnd }} of {{ model.filteredTransactionCount }}
            <span v-if="model.searchQuery && model.filteredTransactionCount !== model.transactions.count" style="color: var(--muted);">
              ({{ model.transactions.count }} total)
            </span>
          </span>
          <div class="pagination-controls" v-if="model.filteredTransactionCount > 0">
            <button class="shortcut-btn" @click="model.goToTransactionPage(1)" :disabled="model.currentTransactionPage === 1">
              First
            </button>
            <button class="shortcut-btn" @click="model.goToPreviousTransactionPage()" :disabled="model.currentTransactionPage === 1">
              Prev
            </button>
            <button
              v-for="page in model.transactionPageButtons"
              :key="page"
              class="shortcut-btn"
              :class="{ active: model.currentTransactionPage === page }"
              @click="model.goToTransactionPage(page)"
            >
              {{ page }}
            </button>
            <button class="shortcut-btn" @click="model.goToNextTransactionPage()" :disabled="model.currentTransactionPage === model.totalTransactionPages">
              Next
            </button>
            <button class="shortcut-btn" @click="model.goToTransactionPage(model.totalTransactionPages)" :disabled="model.currentTransactionPage === model.totalTransactionPages">
              Last
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
};
