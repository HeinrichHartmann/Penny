import { createAccountsViewState } from './accounts.js';

export const AccountsView = {
  name: 'AccountsView',
  props: {
    model: { type: Object, required: true },
    actions: { type: Object, required: true },
    filters: { type: Object, required: true },
    toggleAccount: { type: Function, required: true },
  },
  setup(props) {
    const {
      editingAccountId,
      editingAccountData,
      recordingBalanceForId,
      balanceData,
      startEditingAccount,
      cancelEditingAccount,
      startRecordingBalance,
      cancelRecordingBalance,
    } = createAccountsViewState();

    const saveAccountMetadata = async (accountId) => {
      try {
        const updates = {};
        if (editingAccountData.value.display_name !== undefined) {
          updates.display_name = editingAccountData.value.display_name || null;
        }
        if (editingAccountData.value.iban !== undefined) {
          updates.iban = editingAccountData.value.iban || null;
        }
        if (editingAccountData.value.holder !== undefined) {
          updates.holder = editingAccountData.value.holder || null;
        }
        if (editingAccountData.value.notes !== undefined) {
          updates.notes = editingAccountData.value.notes || null;
        }

        cancelEditingAccount();
        await props.actions.saveAccountMetadata(accountId, updates);
      } catch (error) {
        console.error('Failed to update account:', error);
        alert('Failed to update account: ' + error.message);
      }
    };

    const saveBalanceSnapshot = async (accountId) => {
      try {
        const balanceCents = Math.round(parseFloat(balanceData.value.balance_cents) * 100);
        if (isNaN(balanceCents)) {
          alert('Please enter a valid balance amount');
          return;
        }

        await props.actions.saveBalanceSnapshot(accountId, {
          balance_cents: balanceCents,
          balance_date: balanceData.value.balance_date,
          note: balanceData.value.note || null,
        });

        cancelRecordingBalance();
      } catch (error) {
        console.error('Failed to record balance:', error);
        alert('Failed to record balance: ' + error.message);
      }
    };

    const hideAccount = async (accountId) => {
      if (!confirm('Are you sure you want to hide this account? You can show it again using the "Show Archived" toggle.')) {
        return;
      }
      try {
        await props.actions.archiveAccount(accountId);
      } catch (error) {
        console.error('Failed to hide account:', error);
        alert('Failed to hide account: ' + error.message);
      }
    };

    const formatCurrency = (cents) => {
      if (cents === null || cents === undefined) return null;
      return (cents / 100).toFixed(2);
    };

    return {
      editingAccountId,
      editingAccountData,
      recordingBalanceForId,
      balanceData,
      startEditingAccount,
      cancelEditingAccount,
      saveAccountMetadata,
      startRecordingBalance,
      cancelRecordingBalance,
      saveBalanceSnapshot,
      hideAccount,
      formatCurrency,
    };
  },
  template: `
    <div>
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
        <h2 style="font-size: 1.4rem; margin: 0;">Accounts</h2>
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.9rem;">
          <input
            type="checkbox"
            :checked="model.includeHidden"
            @change="actions.setIncludeHiddenAccounts($event.target.checked)"
            style="cursor: pointer;"
          >
          <span>Show Archived</span>
        </label>
      </div>

      <div v-if="model.loading" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted);">Loading accounts...</p>
      </div>

      <div v-else-if="model.accounts.length === 0" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted);">No accounts imported yet. Import CSVs to see your accounts here.</p>
      </div>

      <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px;">
        <div v-for="acc in model.accounts" :key="acc.id"
          :class="['panel', 'account-card', filters.accounts.includes(acc.id) ? 'active' : 'inactive']"
          :style="{
            padding: '24px',
            transition: 'all 0.2s',
            opacity: acc.hidden ? 0.6 : 1,
            border: acc.hidden ? '2px dashed var(--muted)' : ''
          }">

          <div v-if="editingAccountId === acc.id" style="margin-bottom: 16px;">
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">Display Name</label>
              <input
                v-model="editingAccountData.display_name"
                type="text"
                :placeholder="acc.bank + ' #' + acc.id"
                @keyup.enter="saveAccountMetadata(acc.id)"
                @keyup.escape="cancelEditingAccount"
                style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 0.9rem;"
                autofocus
              >
            </div>
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">IBAN</label>
              <input
                v-model="editingAccountData.iban"
                type="text"
                placeholder="DE89 3704 0044 0532 0130 00"
                @keyup.enter="saveAccountMetadata(acc.id)"
                @keyup.escape="cancelEditingAccount"
                style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 0.9rem;"
              >
            </div>
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">Account Holder</label>
              <input
                v-model="editingAccountData.holder"
                type="text"
                placeholder="John Doe"
                @keyup.enter="saveAccountMetadata(acc.id)"
                @keyup.escape="cancelEditingAccount"
                style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 0.9rem;"
              >
            </div>
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">Notes</label>
              <textarea
                v-model="editingAccountData.notes"
                placeholder="Optional notes..."
                rows="2"
                @keyup.escape="cancelEditingAccount"
                style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 0.9rem; resize: vertical;"
              ></textarea>
            </div>
            <div style="display: flex; gap: 8px;">
              <button
                @click="saveAccountMetadata(acc.id)"
                style="padding: 6px 16px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
                Save Metadata
              </button>
              <button
                @click="cancelEditingAccount"
                style="padding: 6px 16px; background: var(--muted); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
                Cancel
              </button>
            </div>
          </div>

          <div v-else-if="recordingBalanceForId === acc.id" style="margin-bottom: 16px;">
            <h3 style="font-size: 1rem; margin-bottom: 12px;">Record Balance Snapshot</h3>
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">Balance (€)</label>
              <input
                v-model="balanceData.balance_cents"
                type="number"
                step="0.01"
                placeholder="0.00"
                @keyup.enter="saveBalanceSnapshot(acc.id)"
                @keyup.escape="cancelRecordingBalance"
                style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 0.9rem;"
                autofocus
              >
            </div>
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">Date</label>
              <input
                v-model="balanceData.balance_date"
                type="date"
                @keyup.enter="saveBalanceSnapshot(acc.id)"
                @keyup.escape="cancelRecordingBalance"
                style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 0.9rem;"
              >
            </div>
            <div style="margin-bottom: 12px;">
              <label style="display: block; font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">Note (optional)</label>
              <input
                v-model="balanceData.note"
                type="text"
                placeholder="e.g., Monthly balance check"
                @keyup.enter="saveBalanceSnapshot(acc.id)"
                @keyup.escape="cancelRecordingBalance"
                style="width: 100%; padding: 6px 10px; border: 1px solid var(--accent); border-radius: 4px; font-size: 0.9rem;"
              >
            </div>
            <div style="display: flex; gap: 8px;">
              <button
                @click="saveBalanceSnapshot(acc.id)"
                style="padding: 6px 16px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
                Save Balance
              </button>
              <button
                @click="cancelRecordingBalance"
                style="padding: 6px 16px; background: var(--muted); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
                Cancel
              </button>
            </div>
          </div>

          <div v-else>
            <div style="display: flex; align-items: flex-start; gap: 16px; margin-bottom: 16px;">
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
                <div style="font-weight: 600; font-size: 1rem; margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
                  <span>{{ acc.display_name || acc.bank + ' #' + acc.id }}</span>
                  <span v-if="acc.hidden" style="font-size: 0.7rem; padding: 2px 8px; background: var(--muted); color: white; border-radius: 4px;">ARCHIVED</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--muted); margin-bottom: 4px;">
                  {{ acc.bank }}
                  <span v-if="acc.iban"> · {{ acc.iban.slice(-8) }}</span>
                </div>
                <div v-if="acc.holder" style="font-size: 0.75rem; color: var(--muted); margin-bottom: 4px;">
                  {{ acc.holder }}
                </div>
                <div style="display: flex; gap: 16px; font-size: 0.75rem; color: var(--muted);">
                  <span>{{ acc.transaction_count }} transactions</span>
                  <span>{{ acc.balance_snapshot_count }} balance snapshots</span>
                  <span v-if="acc.subaccounts?.length">
                    {{ acc.subaccounts.join(', ') }}
                  </span>
                </div>
                <div v-if="acc.balance_cents !== null && acc.balance_cents !== undefined" style="font-size: 0.85rem; margin-top: 8px; padding: 6px 10px; background: #f5f0e8; border-radius: 4px;">
                  <strong>Balance:</strong> €{{ formatCurrency(acc.balance_cents) }}
                  <span v-if="acc.balance_date" style="color: var(--muted); margin-left: 8px;">
                    ({{ acc.balance_date }})
                  </span>
                </div>
                <div v-if="acc.notes" style="font-size: 0.75rem; color: var(--muted); margin-top: 8px; font-style: italic;">
                  {{ acc.notes }}
                </div>
              </div>
            </div>

            <div style="display: flex; gap: 8px; margin-top: 12px;">
              <button
                @click="startEditingAccount(acc)"
                style="flex: 1; padding: 6px 12px; background: #e8dcc8; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">
                ✏️ Edit Metadata
              </button>
              <button
                @click="startRecordingBalance(acc)"
                style="flex: 1; padding: 6px 12px; background: #e8dcc8; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem;">
                💰 Record Balance
              </button>
            </div>
            <div v-if="!acc.hidden" style="display: flex; gap: 8px; margin-top: 8px;">
              <button
                @click="hideAccount(acc.id)"
                style="width: 100%; padding: 6px 12px; background: #d4c4b0; border: none; border-radius: 4px; cursor: pointer; font-size: 0.8rem; color: #6b4a29;">
                🗄️ Archive Account
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
};
