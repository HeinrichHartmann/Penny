import { computed, reactive } from 'vue/dist/vue.esm-bundler.js';

export const createRulesViewState = ({ fetchRules, saveRules, runRules }) => {
  const rulesState = reactive({
    path: '',
    directory: '',
    exists: false,
    content: '',
    originalContent: '',
    loading: false,
    saving: false,
    running: false,
    error: null,
    saveMessage: null,
    lastRunAt: null,
    logs: [],
    stats: null,
  });

  const loadRules = async () => {
    rulesState.loading = true;
    rulesState.error = null;
    try {
      const data = await fetchRules();
      rulesState.path = data.path;
      rulesState.directory = data.directory;
      rulesState.exists = data.exists;
      rulesState.content = data.content || '';
      rulesState.originalContent = data.content || '';
      rulesState.lastRunAt = data.latest_run?.started_at || null;
      rulesState.logs = data.latest_run?.logs || [];
      rulesState.stats = data.latest_run?.stats || null;
      if (data.latest_run?.status === 'error') {
        rulesState.error = 'Classification failed - see logs below';
      }
    } catch (error) {
      rulesState.error = error.message;
    } finally {
      rulesState.loading = false;
    }
  };

  const runClassification = async () => {
    rulesState.running = true;
    rulesState.logs = [];
    rulesState.stats = null;
    try {
      const result = await runRules();
      rulesState.lastRunAt = result.started_at || null;
      rulesState.logs = result.logs || [];
      rulesState.stats = result.stats;
      rulesState.error = result.status === 'error' ? 'Classification failed - see logs below' : null;
      return result.status !== 'error';
    } catch (error) {
      rulesState.error = error.message;
      rulesState.logs = [{ level: 'error', message: error.message }];
      return false;
    } finally {
      rulesState.running = false;
    }
  };

  const saveRulesContent = async () => {
    rulesState.saving = true;
    rulesState.error = null;
    rulesState.saveMessage = null;
    try {
      await saveRules(rulesState.content);
      rulesState.originalContent = rulesState.content;
      rulesState.saveMessage = 'Saved successfully';
      await runClassification();
      return true;
    } catch (error) {
      rulesState.error = error.message;
      return false;
    } finally {
      rulesState.saving = false;
    }
  };

  const reloadRules = async () => {
    await loadRules();
  };

  const rulesHasChanges = computed(() => rulesState.content !== rulesState.originalContent);

  return {
    rulesState,
    loadRules,
    saveRulesContent,
    runClassification,
    reloadRules,
    rulesHasChanges,
  };
};
