import { onMounted } from 'vue/dist/vue.esm-bundler.js';

import { SelectorHeader } from '../components/SelectorHeader.js';
import { formatCurrency } from '../utils/format.js';

export const BalanceView = {
  name: 'BalanceView',
  components: {
    SelectorHeader,
  },
  props: {
    model: { type: Object, required: true },
  },
  setup(props) {
    onMounted(async () => {
      await props.model.loadValueHistory();
    });

    return {
      formatCurrency,
    };
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Account Balance History</h2>

      <selector-header
        :state="model.selectorState"
        :actions="model.selectorActions"
      ></selector-header>

      <div v-if="model.valueHistory && model.valueHistory.value_points && model.valueHistory.value_points.length > 0" class="panel" style="margin-bottom:20px;">
        <div class="txn-header-bar">
          <div class="txn-header">
            Account Value Over Time
            <span class="sub" v-if="model.latestBalance !== null">
              Current Balance: {{ formatCurrency(model.latestBalance) }}
            </span>
          </div>
          <div class="btn-group wrap">
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.9rem;">
              <input
                type="checkbox"
                :checked="model.showVolume"
                @change="model.setShowVolume($event.target.checked)"
                style="cursor: pointer;"
              >
              <span>Show Transaction Volume</span>
            </label>
          </div>
        </div>
        <div :ref="model.setBalanceChartEl" style="width:100%; height:520px;"></div>
      </div>

      <div v-else-if="!model.loading" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted);">
          No balance data available for the selected accounts and date range.
          <br>
          Record balance snapshots in the Accounts view to enable balance tracking.
        </p>
      </div>

      <div v-if="model.loading" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted);">Loading balance history...</p>
      </div>

      <div v-if="model.valueHistory && model.valueHistory.balance_snapshots && model.valueHistory.balance_snapshots.length > 0" class="panel" style="margin-top: 20px;">
        <div class="txn-header">
          Recorded Balance Snapshots
          <span class="sub">{{ model.valueHistory.balance_snapshots.length }} snapshots</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Account</th>
              <th>Subaccount</th>
              <th class="text-right">Balance</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="snapshot in model.valueHistory.balance_snapshots" :key="snapshot.date + snapshot.account_id">
              <td>{{ snapshot.date }}</td>
              <td>Account #{{ snapshot.account_id }}</td>
              <td>{{ snapshot.subaccount_type || '-' }}</td>
              <td class="text-right">{{ formatCurrency(snapshot.balance_cents) }}</td>
              <td>{{ snapshot.note || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="model.valueHistory && model.valueHistory.value_points && model.valueHistory.value_points.length > 0" class="panel" style="margin-top: 20px;">
        <div class="txn-header">
          Transactions
          <span class="sub">{{ model.valueHistory.value_points.length }} transactions</span>
        </div>
        <div class="txn-table-wrap" style="max-height: 400px; overflow-y: auto;">
          <table>
            <thead>
              <tr>
                <th style="width:90px">Date</th>
                <th>Description</th>
                <th class="text-right" style="width:100px">Amount</th>
                <th class="text-right" style="width:120px">Balance</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(tx, index) in model.valueHistory.value_points" :key="tx.fingerprint || index">
                <td>{{ tx.date }}</td>
                <td style="font-size: 0.85rem;">{{ tx.payee }}</td>
                <td class="text-right" :style="{ color: tx.amount_cents >= 0 ? 'var(--income-color)' : '#c1121f' }">
                  {{ formatCurrency(tx.amount_cents) }}
                </td>
                <td class="text-right" :style="{ fontWeight: tx.is_snapshot ? 'bold' : 'normal' }">
                  {{ formatCurrency(tx.total_balance) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
};
