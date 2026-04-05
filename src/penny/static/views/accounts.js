import { ref } from 'vue/dist/vue.esm-bundler.js';

export const createAccountsViewState = () => {
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

  return {
    editingAccountId,
    editingAccountData,
    recordingBalanceForId,
    balanceData,
    startEditingAccount,
    cancelEditingAccount,
    startRecordingBalance,
    cancelRecordingBalance,
  };
};
