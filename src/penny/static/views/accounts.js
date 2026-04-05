import { ref } from 'vue/dist/vue.esm-bundler.js';

export const createAccountsViewState = ({
  fetchAccounts,
  updateAccount,
  recordBalanceSnapshot,
  deleteAccount,
  rehydrateApp,
}) => {
  const accountsList = ref([]);
  const accountsLoading = ref(false);
  const includeHidden = ref(false);
  const editingAccountId = ref(null);
  const editingAccountData = ref({
    display_name: '',
    iban: '',
    holder: '',
    notes: '',
  });
  const recordingBalanceForId = ref(null);
  const balanceData = ref({
    balance_cents: '',
    balance_date: new Date().toISOString().split('T')[0],
    note: '',
  });

  const loadAccounts = async () => {
    accountsLoading.value = true;
    try {
      const data = await fetchAccounts(includeHidden.value);
      accountsList.value = data.accounts;
    } finally {
      accountsLoading.value = false;
    }
  };

  const startEditingAccount = (account) => {
    editingAccountId.value = account.id;
    editingAccountData.value = {
      display_name: account.display_name || '',
      iban: account.iban || '',
      holder: account.holder || '',
      notes: account.notes || '',
    };
  };

  const cancelEditingAccount = () => {
    editingAccountId.value = null;
    editingAccountData.value = {
      display_name: '',
      iban: '',
      holder: '',
      notes: '',
    };
  };

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
      await updateAccount(accountId, updates);
      await rehydrateApp();
    } catch (error) {
      console.error('Failed to update account:', error);
      alert('Failed to update account: ' + error.message);
    }
  };

  const startRecordingBalance = (account) => {
    recordingBalanceForId.value = account.id;
    const currentBalance = account.balance_cents || 0;
    balanceData.value = {
      balance_cents: currentBalance === 0 ? '' : (currentBalance / 100).toFixed(2),
      balance_date: account.balance_date || new Date().toISOString().split('T')[0],
      note: '',
    };
  };

  const cancelRecordingBalance = () => {
    recordingBalanceForId.value = null;
    balanceData.value = {
      balance_cents: '',
      balance_date: new Date().toISOString().split('T')[0],
      note: '',
    };
  };

  const saveBalanceSnapshot = async (accountId) => {
    try {
      const balanceCents = Math.round(parseFloat(balanceData.value.balance_cents) * 100);
      if (isNaN(balanceCents)) {
        alert('Please enter a valid balance amount');
        return;
      }

      await recordBalanceSnapshot(accountId, {
        balance_cents: balanceCents,
        balance_date: balanceData.value.balance_date,
        note: balanceData.value.note || null,
      });

      cancelRecordingBalance();
      await rehydrateApp();
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
      await deleteAccount(accountId);
      await rehydrateApp();
    } catch (error) {
      console.error('Failed to hide account:', error);
      alert('Failed to hide account: ' + error.message);
    }
  };

  const toggleIncludeHidden = async () => {
    includeHidden.value = !includeHidden.value;
    await loadAccounts();
  };

  return {
    accountsList,
    accountsLoading,
    includeHidden,
    editingAccountId,
    editingAccountData,
    recordingBalanceForId,
    balanceData,
    loadAccounts,
    startEditingAccount,
    cancelEditingAccount,
    saveAccountMetadata,
    startRecordingBalance,
    cancelRecordingBalance,
    saveBalanceSnapshot,
    hideAccount,
    toggleIncludeHidden,
  };
};
