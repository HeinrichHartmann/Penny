import { onMounted } from 'vue/dist/vue.esm-bundler.js';

import { fetchAccounts, updateAccount } from '../api.js';
import { createAccountsViewState } from './accounts.js';

export const AccountsView = {
  name: 'AccountsView',
  props: {
    filters: { type: Object, required: true },
    toggleAccount: { type: Function, required: true },
    refreshMeta: { type: Function, required: true },
  },
  setup(props) {
    const {
      accountsList,
      accountsLoading,
      editingAccountId,
      editingAccountName,
      loadAccounts,
      startEditingAccount,
      cancelEditingAccount,
      saveAccountName,
    } = createAccountsViewState({
      fetchAccounts,
      updateAccount,
      refreshMeta: props.refreshMeta,
    });

    onMounted(async () => {
      await loadAccounts();
    });

    return {
      accountsList,
      accountsLoading,
      editingAccountId,
      editingAccountName,
      loadAccounts,
      startEditingAccount,
      cancelEditingAccount,
      saveAccountName,
    };
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Accounts</h2>

      <div v-if="accountsLoading" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted);">Loading accounts...</p>
      </div>

      <div v-else-if="accountsList.length === 0" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted);">No accounts imported yet. Import CSVs to see your accounts here.</p>
      </div>

      <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px;">
        <div v-for="acc in accountsList" :key="acc.id"
          :class="['panel', 'account-card', filters.accounts.includes(acc.id) ? 'active' : 'inactive']"
          style="padding: 24px; transition: all 0.2s;">
          <div style="display: flex; align-items: flex-start; gap: 16px;">
            <div
              @click="toggleAccount(acc.id)"
              :style="{
                width: '56px',
                height: '56px',
                borderRadius: '8px',
                background: filters.accounts.includes(acc.id) ? 'linear-gradient(135deg, #845b31 0%, #6b4a29 100%)' : '#e8dcc8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '1.5rem',
                transition: 'all 0.2s',
                flexShrink: 0,
                cursor: 'pointer',
                boxShadow: filters.accounts.includes(acc.id) ? '0 4px 12px rgba(132, 91, 49, 0.3)' : 'none'
              }">
              {{ filters.accounts.includes(acc.id) ? '💳' : '🔒' }}
            </div>
            <div style="flex: 1; min-width: 0;">
              <div v-if="editingAccountId === acc.id" style="margin-bottom: 8px;">
                <input
                  v-model="editingAccountName"
                  type="text"
                  :placeholder="acc.bank + ' #' + acc.id"
                  @keyup.enter="saveAccountName(acc.id)"
                  @keyup.escape="cancelEditingAccount"
                  style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 1rem; font-weight: 600;"
                  autofocus
                >
                <div style="margin-top: 8px; display: flex; gap: 8px;">
                  <button
                    @click="saveAccountName(acc.id)"
                    style="padding: 4px 12px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">
                    Save
                  </button>
                  <button
                    @click="cancelEditingAccount"
                    style="padding: 4px 12px; background: var(--muted); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">
                    Cancel
                  </button>
                </div>
              </div>
              <div v-else>
                <div
                  @click.stop="startEditingAccount(acc)"
                  style="font-weight: 600; font-size: 1rem; margin-bottom: 4px; cursor: pointer;"
                  title="Click to edit name">
                  {{ acc.display_name || acc.bank + ' #' + acc.id }}
                  <span style="font-size: 0.7rem; color: var(--muted); margin-left: 4px;">✏️</span>
                </div>
              </div>
              <div style="font-size: 0.8rem; color: var(--muted); margin-bottom: 8px;">
                {{ acc.bank }}
                <span v-if="acc.iban"> · {{ acc.iban.slice(-8) }}</span>
              </div>
              <div style="display: flex; gap: 16px; font-size: 0.75rem; color: var(--muted);">
                <span>{{ acc.transaction_count }} transactions</span>
                <span v-if="acc.subaccounts?.length">
                  {{ acc.subaccounts.join(', ') }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
};
