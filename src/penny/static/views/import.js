import { reactive } from 'vue/dist/vue.esm-bundler.js';

export const createImportViewState = ({ uploadCsv, loadAccounts, refreshMeta }) => {
  const importState = reactive({
    isDragging: false,
    isUploading: false,
    lastResult: null,
    error: null,
  });

  const uploadFiles = async (files) => {
    importState.isUploading = true;
    importState.error = null;
    importState.lastResult = null;

    try {
      const results = [];
      for (const file of files) {
        const result = await uploadCsv(file);
        results.push(result);
      }

      importState.lastResult = results.length === 1 ? results[0] : results;
      await Promise.all([loadAccounts(), refreshMeta()]);
    } catch (error) {
      importState.error = error.message;
    } finally {
      importState.isUploading = false;
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    importState.isDragging = true;
  };

  const handleDragLeave = () => {
    importState.isDragging = false;
  };

  const handleDrop = async (event) => {
    event.preventDefault();
    importState.isDragging = false;

    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      await uploadFiles(files);
    }
  };

  const handleFileSelect = async (event) => {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
      await uploadFiles(files);
    }
    event.target.value = '';
  };

  const resetImportState = () => {
    importState.lastResult = null;
    importState.error = null;
  };

  return {
    importState,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleFileSelect,
    resetImportState,
  };
};
