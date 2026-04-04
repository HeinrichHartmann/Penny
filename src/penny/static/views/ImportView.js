import { uploadCsv } from '../api.js';
import { createImportViewState } from './import.js';

export const ImportView = {
  name: 'ImportView',
  emits: ['imported'],
  setup(props, { emit }) {
    const {
      importState,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      handleFileSelect,
    } = createImportViewState({
      uploadCsv,
      afterUpload: async () => {
        emit('imported');
      },
    });

    return {
      importState,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      handleFileSelect,
    };
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Import</h2>

      <div
        class="panel"
        :style="{
          padding: '60px 40px',
          textAlign: 'center',
          border: importState.isDragging ? '2px dashed var(--accent)' : '2px dashed transparent',
          background: importState.isDragging ? 'rgba(132, 91, 49, 0.05)' : 'var(--panel-bg)',
          transition: 'all 0.2s'
        }"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
      >
        <div v-if="importState.isUploading" style="font-size: 1.2rem; color: var(--accent);">
          Importing...
        </div>
        <template v-else>
          <div style="font-size: 3rem; margin-bottom: 16px; opacity: 0.4;">
            {{ importState.isDragging ? '📥' : '📂' }}
          </div>
          <p style="color: var(--muted); margin-bottom: 12px;">
            Drag & drop CSV files from your bank
          </p>
          <p style="color: var(--muted); font-size: 0.85rem; margin-bottom: 16px;">
            Supports: Comdirect, Sparkasse, and more
          </p>
          <label style="display: inline-block; padding: 8px 16px; background: var(--accent); color: white; border-radius: 4px; cursor: pointer;">
            Choose Files
            <input type="file" accept=".csv" multiple @change="handleFileSelect" style="display: none;">
          </label>
        </template>
      </div>

      <div v-if="importState.error" class="panel" style="margin-top: 16px; padding: 16px; background: #fee; border-left: 3px solid #c00;">
        <strong style="color: #c00;">Import Error:</strong> {{ importState.error }}
      </div>

      <div v-if="importState.lastResult" class="panel" style="margin-top: 16px; padding: 20px;">
        <h3 style="margin-bottom: 12px; color: var(--accent);">Import Successful</h3>
        <div style="display: grid; gap: 8px; font-size: 0.9rem;">
          <div><strong>File:</strong> {{ importState.lastResult.filename }}</div>
          <div><strong>Parser:</strong> {{ importState.lastResult.parser }}</div>
          <div><strong>Account:</strong> {{ importState.lastResult.account?.label }}</div>
          <div v-if="importState.lastResult.account?.is_new" style="color: var(--accent);">
            (New account created)
          </div>
          <div style="margin-top: 8px;">
            <strong>Transactions:</strong>
            {{ importState.lastResult.transactions?.new }} new,
            {{ importState.lastResult.transactions?.duplicates }} duplicates skipped
          </div>
        </div>
      </div>
    </div>
  `,
};
