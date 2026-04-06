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

    const formatFilename = (imp) => {
      // For ingest entries, show the CSV filenames
      if (imp.filenames && imp.filenames.length > 0) {
        return imp.filenames.join(', ');
      }
      return imp.filename || '—';
    };

    const formatBalanceDetails = (imp) => {
      // Parse "4 snapshot(s) for 1 account(s)" into cleaner format
      const label = imp.account_label || '';
      const match = label.match(/(\d+) snapshot.*?(\d+) account/);
      if (match) {
        const snapshots = parseInt(match[1]);
        const accounts = parseInt(match[2]);
        return `${snapshots} snapshot${snapshots !== 1 ? 's' : ''}, ${accounts} account${accounts !== 1 ? 's' : ''}`;
      }
      return label;
    };

    return {
      dragState,
      handleDragOver,
      handleDragLeave,
      handleDrop,
      handleFileSelect,
      formatDate,
      formatFilename,
      formatBalanceDetails,
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

        <div class="panel" style="padding: 0; overflow: hidden;">
          <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
            <thead>
              <tr style="background: var(--panel-bg); border-bottom: 1px solid var(--border);">
                <th style="padding: 12px 16px; text-align: left; font-weight: 600; color: var(--muted); width: 40px;"></th>
                <th style="padding: 12px 16px; text-align: left; font-weight: 600; color: var(--muted);">File</th>
                <th style="padding: 12px 8px; text-align: left; font-weight: 600; color: var(--muted);">Type</th>
                <th style="padding: 12px 8px; text-align: left; font-weight: 600; color: var(--muted);">Details</th>
                <th style="padding: 12px 16px; text-align: right; font-weight: 600; color: var(--muted);">Date</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="imp in model.history" :key="imp.sequence"
                  style="border-bottom: 1px solid var(--border);"
                  :style="{ opacity: imp.enabled ? 1 : 0.5 }">
                <td style="padding: 12px 16px; text-align: center;">
                  <input
                    type="checkbox"
                    :checked="imp.enabled"
                    @change="actions.toggleImportEntryEnabled(imp.sequence)"
                    style="cursor: pointer;"
                  >
                </td>
                <td style="padding: 12px 16px;">
                  <div style="font-weight: 500; word-break: break-word;">
                    {{ formatFilename(imp) }}
                  </div>
                  <div v-if="imp.warning" style="font-size: 0.8rem; color: #856404; margin-top: 4px;">
                    {{ imp.warning }}
                  </div>
                </td>
                <td style="padding: 12px 8px;">
                  <span :style="{
                    display: 'inline-block',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '0.8rem',
                    background: imp.type === 'ingest' ? 'rgba(132, 91, 49, 0.1)' :
                               imp.type === 'rules' ? 'rgba(100, 100, 200, 0.1)' :
                               'rgba(100, 200, 100, 0.1)',
                    color: imp.type === 'ingest' ? 'var(--accent)' :
                           imp.type === 'rules' ? '#5555aa' : '#339933'
                  }">
                    {{ imp.type === 'ingest' ? 'CSV' : imp.type === 'rules' ? 'Rules' : 'Balance' }}
                  </span>
                </td>
                <td style="padding: 12px 8px; color: var(--muted); font-size: 0.85rem;">
                  <template v-if="imp.type === 'ingest'">
                    {{ imp.parser }} → {{ imp.account_label || 'Unknown' }}
                  </template>
                  <template v-else-if="imp.type === 'balance_anchors'">
                    {{ formatBalanceDetails(imp) }}
                  </template>
                  <template v-else>
                    Classification rules
                  </template>
                </td>
                <td style="padding: 12px 16px; text-align: right; color: var(--muted); font-size: 0.85rem; white-space: nowrap;">
                  {{ formatDate(imp.timestamp) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
};
