import { createImportViewState } from './import.js';

export const ImportView = {
  name: 'ImportView',
  props: {
    model: { type: Object, required: true },
    actions: { type: Object, required: true },
  },
  setup(props) {
    const {
      dragState,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      handleFileSelect,
    } = createImportViewState({
      uploadSelectedFiles: props.actions.uploadSelectedFiles,
    });

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

    return {
      dragState,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      handleFileSelect,
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
          border: dragState.isDragging ? '2px dashed var(--accent)' : '2px dashed transparent',
          background: dragState.isDragging ? 'rgba(132, 91, 49, 0.05)' : 'var(--panel-bg)',
          transition: 'all 0.2s'
        }"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
      >
        <div v-if="model.isUploading" style="font-size: 1.2rem; color: var(--accent);">
          Importing...
        </div>
        <template v-else>
          <div style="font-size: 3rem; margin-bottom: 16px; opacity: 0.4;">
            {{ dragState.isDragging ? '📥' : '📂' }}
          </div>
          <p style="color: var(--muted); margin-bottom: 12px;">
            Drag & drop CSV files, rules.py, or balance-anchors.tsv
          </p>
          <p style="color: var(--muted); font-size: 0.85rem; margin-bottom: 16px;">
            CSV: Comdirect, Sparkasse | TSV: Balance snapshots
          </p>
          <label style="display: inline-block; padding: 8px 16px; background: var(--accent); color: white; border-radius: 4px; cursor: pointer;">
            Choose Files
            <input type="file" accept=".csv,.py,.tsv" multiple @change="handleFileSelect" style="display: none;">
          </label>
        </template>
      </div>

      <div v-if="model.error" class="panel" style="margin-top: 16px; padding: 16px; background: #fee; border-left: 3px solid #c00;">
        <strong style="color: #c00;">Import Error:</strong> {{ model.error }}
      </div>

      <div v-if="model.lastResult" class="panel" style="margin-top: 16px; padding: 20px;">
        <h3 style="margin-bottom: 12px; color: var(--accent);">
          {{ model.lastResult.type === 'rules' ? 'Rules Updated' : 'Import Successful' }}
        </h3>
        <div style="display: grid; gap: 8px; font-size: 0.9rem;">
          <div><strong>File:</strong> {{ model.lastResult.filename }}</div>
          <template v-if="model.lastResult.type === 'rules'">
            <div><strong>Type:</strong> Classification Rules</div>
            <div><strong>Status:</strong> {{ model.lastResult.status }}</div>
            <div style="margin-top: 8px; color: var(--muted); font-size: 0.85rem;">
              Rules file has been saved. Go to the Rules page to review and run classifications.
            </div>
          </template>
          <template v-else>
            <div><strong>Parser:</strong> {{ model.lastResult.parser }}</div>
            <div><strong>Account:</strong> {{ model.lastResult.account?.label }}</div>
            <div v-if="model.lastResult.account?.is_new" style="color: var(--accent);">
              (New account created)
            </div>
            <div style="margin-top: 8px;">
              <strong>Transactions:</strong>
              {{ model.lastResult.transactions?.new }} new,
              {{ model.lastResult.transactions?.duplicates }} duplicates skipped
            </div>
          </template>
        </div>
      </div>

      <div style="margin-top: 32px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <h3 style="font-size: 1.1rem; color: var(--muted); margin: 0;">Import History</h3>
          <button
            @click="actions.rebuildProjection"
            :disabled="model.rebuilding"
            style="padding: 8px 16px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem;"
            :style="{ opacity: model.rebuilding ? 0.6 : 1 }"
          >
            {{ model.rebuilding ? 'Rebuilding...' : 'Rebuild Database' }}
          </button>
        </div>

        <div v-if="model.rebuildResult" class="panel" style="margin-bottom: 16px; padding: 16px; background: #d4edda; border-left: 3px solid #155724;">
          <strong style="color: #155724;">Database Rebuilt:</strong>
          {{ model.rebuildResult.entries_processed }} entries processed
        </div>

        <div v-if="model.historyLoading" class="panel" style="padding: 40px; text-align: center;">
          <p style="color: var(--muted);">Loading import history...</p>
        </div>

        <div v-else-if="model.history.length === 0" class="panel" style="padding: 40px; text-align: center;">
          <p style="color: var(--muted); margin-bottom: 20px;">No imports yet. Upload a CSV file to get started.</p>
          <button
            @click="actions.importDemo"
            :disabled="model.importingDemo"
            style="padding: 12px 24px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem;"
            :style="{ opacity: model.importingDemo ? 0.6 : 1 }"
          >
            {{ model.importingDemo ? 'Importing Demo Data...' : 'Import Demo Data' }}
          </button>
        </div>

        <div v-else style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px;">
          <div v-for="imp in model.history" :key="imp.sequence" class="panel" style="padding: 20px;" :style="{ opacity: imp.enabled ? 1 : 0.5 }">
            <div style="display: flex; align-items: flex-start; gap: 16px;">
              <div style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
                <div :style="{
                  width: '48px',
                  height: '48px',
                  borderRadius: '8px',
                  background: imp.enabled ? 'linear-gradient(135deg, #845b31 0%, #6b4a29 100%)' : '#ccc',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1.3rem',
                  flexShrink: 0
                }">
                  {{ imp.status === 'applied' ? '✓' : '✗' }}
                </div>
                <label style="display: flex; align-items: center; gap: 4px; cursor: pointer; font-size: 0.75rem; color: var(--muted);">
                  <input
                    type="checkbox"
                    :checked="imp.enabled"
                    @change="actions.toggleImportEntryEnabled(imp.sequence)"
                    style="cursor: pointer;"
                  >
                  Enabled
                </label>
              </div>
              <div style="flex: 1; min-width: 0;">
                <div style="font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; word-break: break-word;">
                  {{ imp.filenames.join(', ') || 'Unknown file' }}
                </div>
                <div style="font-size: 0.8rem; color: var(--muted); margin-bottom: 8px;">
                  {{ formatDate(imp.timestamp) }}
                </div>
                <div v-if="imp.warning" style="font-size: 0.8rem; color: #856404; background: #fff3cd; padding: 4px 8px; border-radius: 4px; margin-bottom: 8px;">
                  {{ imp.warning }}
                </div>
                <div style="display: flex; gap: 12px; flex-wrap: wrap; font-size: 0.8rem;">
                  <span style="color: var(--muted);">Type: <strong style="color: var(--text);">{{ imp.type }}</strong></span>
                  <span v-if="imp.parser" style="color: var(--muted);">Parser: <strong style="color: var(--text);">{{ imp.parser }}</strong></span>
                  <span v-if="imp.account_label" style="color: var(--muted);">Account: <strong style="color: var(--text);">{{ imp.account_label }}</strong></span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
};
