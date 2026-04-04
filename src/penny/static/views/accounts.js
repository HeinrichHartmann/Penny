import { ref } from 'vue/dist/vue.esm-bundler.js';

export const createAccountsViewState = ({ fetchAccounts, updateAccount, refreshMeta }) => {
  const accountsList = ref([]);
  const accountsLoading = ref(false);
  const editingAccountId = ref(null);
  const editingAccountName = ref('');

  const loadAccounts = async () => {
    accountsLoading.value = true;
    try {
      const data = await fetchAccounts();
      accountsList.value = data.accounts;
    } finally {
      accountsLoading.value = false;
    }
  };

  const startEditingAccount = (account) => {
    editingAccountId.value = account.id;
    editingAccountName.value = account.display_name || '';
  };

  const cancelEditingAccount = () => {
    editingAccountId.value = null;
    editingAccountName.value = '';
  };

  const saveAccountName = async (accountId) => {
    try {
      await updateAccount(accountId, { display_name: editingAccountName.value || null });
      await Promise.all([loadAccounts(), refreshMeta()]);
      cancelEditingAccount();
    } catch (error) {
      console.error('Failed to update account:', error);
    }
  };

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
};
