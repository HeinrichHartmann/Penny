import { onMounted, ref } from 'vue/dist/vue.esm-bundler.js';

import { uploadCsv, fetchImportHistory } from '../api.js';
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
        await loadImportHistory();
      },
    });

    const importHistory = ref([]);
    const historyLoading = ref(false);

    const loadImportHistory = async () => {
      historyLoading.value = true;
      try {
        const data = await fetchImportHistory();
        importHistory.value = data.imports || [];
      } catch (error) {
        console.error('Failed to load import history:', error);
        importHistory.value = [];
      } finally {
        historyLoading.value = false;
      }
    };

    const formatDate = (timestamp) => {
      if (!timestamp) return '';
      try {
        const date = new Date(timestamp);
        return date.toLocaleDateString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        });
      } catch {
        return timestamp;
      }
    };

    onMounted(async () => {
      await loadImportHistory();
    });

    return {
      importState,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      handleFileSelect,
      importHistory,
      historyLoading,
      formatDate,
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

      <!-- Import History Section -->
      <div style="margin-top: 32px;">
        <h3 style="font-size: 1.1rem; margin-bottom: 16px; color: var(--muted);">Import History</h3>

        <div v-if="historyLoading" class="panel" style="padding: 40px; text-align: center;">
          <p style="color: var(--muted);">Loading import history...</p>
        </div>

        <div v-else-if="importHistory.length === 0" class="panel" style="padding: 40px; text-align: center;">
          <p style="color: var(--muted);">No imports yet. Upload a CSV file to get started.</p>
        </div>

        <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px;">
          <div v-for="imp in importHistory" :key="imp.sequence" class="panel" style="padding: 20px;">
            <div style="display: flex; align-items: flex-start; gap: 16px;">
              <div style="
                width: 48px;
                height: 48px;
                border-radius: 8px;
                background: linear-gradient(135deg, #845b31 0%, #6b4a29 100%);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.3rem;
                flex-shrink: 0;
              ">
                {{ imp.status === 'applied' ? '✓' : '✗' }}
              </div>
              <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; word-break: break-word;">
                  {{ imp.filenames.join(', ') || 'Unknown file' }}
                </div>
                <div style="font-size: 0.8rem; color: var(--muted); margin-bottom: 8px;">
                  {{ formatDate(imp.timestamp) }}
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 8px; font-size: 0.75rem;">
                  <span style="padding: 2px 8px; background: #e8dcc8; border-radius: 4px;">
                    {{ imp.parser }}
                  </span>
                  <span v-if="imp.account_label" style="padding: 2px 8px; background: #e8dcc8; border-radius: 4px;">
                    {{ imp.account_label }}
                  </span>
                  <span :style="{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: imp.status === 'applied' ? '#d4edda' : '#f8d7da',
                    color: imp.status === 'applied' ? '#155724' : '#721c24'
                  }">
                    {{ imp.status === 'applied' ? 'Applied' : 'Failed' }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
};
