export const RulesView = {
  name: 'RulesView',
  props: {
    model: { type: Object, required: true },
    actions: { type: Object, required: true },
  },
  setup() {
    const formatDateTime = (timestamp) => {
      if (!timestamp) return '';
      try {
        return new Date(timestamp).toLocaleString('en-US', {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        });
      } catch {
        return timestamp;
      }
    };

    return {
      formatDateTime,
    };
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Classification Rules</h2>

      <div class="panel" style="padding: 12px 16px; margin-bottom: 16px; display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 200px;">
          <div style="font-size: 0.75rem; color: var(--muted); margin-bottom: 2px;">Rules File</div>
          <div style="font-family: monospace; font-size: 0.85rem; word-break: break-all;">{{ model.path }}</div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button
            @click="actions.reloadRulesView"
            :disabled="model.loading"
            style="padding: 6px 12px; background: var(--panel-bg); border: 1px solid var(--border); border-radius: 4px; cursor: pointer; font-size: 0.85rem;"
            title="Reload from disk">
            {{ model.loading ? 'Loading...' : 'Reload' }}
          </button>
          <button
            @click="actions.saveRulesContent"
            :disabled="model.saving || !model.hasChanges"
            :style="{
              padding: '6px 12px',
              background: model.hasChanges ? 'var(--accent)' : 'var(--panel-bg)',
              color: model.hasChanges ? 'white' : 'var(--muted)',
              border: model.hasChanges ? 'none' : '1px solid var(--border)',
              borderRadius: '4px',
              cursor: model.hasChanges ? 'pointer' : 'not-allowed',
              fontSize: '0.85rem'
            }"
            title="Save changes">
            {{ model.saving ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>

      <div v-if="model.error" class="panel" style="padding: 12px 16px; margin-bottom: 16px; background: #fee; border-left: 3px solid #c00;">
        <strong style="color: #c00;">Error:</strong> {{ model.error }}
      </div>
      <div v-if="model.saveMessage" class="panel" style="padding: 12px 16px; margin-bottom: 16px; background: #efe; border-left: 3px solid #0a0;">
        {{ model.saveMessage }}
      </div>
      <div v-if="model.hasChanges" style="margin-bottom: 8px; font-size: 0.8rem; color: var(--accent);">
        Unsaved changes
      </div>

      <div v-if="model.loading" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted);">Loading rules...</p>
      </div>

      <div v-else-if="!model.exists" class="panel" style="padding: 40px; text-align: center;">
        <p style="color: var(--muted); margin-bottom: 12px;">No rules file found at:</p>
        <p style="font-family: monospace; font-size: 0.85rem;">{{ model.path }}</p>
        <p style="color: var(--muted); margin-top: 12px; font-size: 0.85rem;">
          Create a rules.py file to define classification rules.
        </p>
      </div>

      <div v-else class="panel" style="padding: 0; overflow: hidden;">
        <textarea
          :value="model.content"
          @input="actions.updateRulesDraft($event.target.value)"
          style="width: 100%; height: 400px; padding: 16px; border: none; resize: vertical; font-family: 'SF Mono', Monaco, Consolas, monospace; font-size: 13px; line-height: 1.5; background: var(--panel-bg); color: var(--text); outline: none;"
          spellcheck="false"
        ></textarea>
      </div>

      <div class="panel" style="margin-top: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
          <div>
            <h3 style="font-size: 1rem; margin: 0;">Classification Log</h3>
            <div v-if="model.lastRunAt" style="font-size: 0.75rem; color: var(--muted); margin-top: 4px;">
              Last run: {{ formatDateTime(model.lastRunAt) }}
            </div>
          </div>
          <button
            @click="actions.runClassification"
            :disabled="model.running"
            style="padding: 6px 12px; background: var(--accent); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem;">
            {{ model.running ? 'Running...' : 'Run Classification' }}
          </button>
        </div>

        <div v-if="model.stats" style="display: flex; gap: 16px; margin-bottom: 12px; padding: 12px; background: var(--bg); border-radius: 6px;">
          <div>
            <span style="color: var(--muted); font-size: 0.75rem;">Rules</span>
            <div style="font-size: 1.1rem; font-weight: 600;">{{ model.stats.rules_count }}</div>
          </div>
          <div>
            <span style="color: var(--muted); font-size: 0.75rem;">Transactions</span>
            <div style="font-size: 1.1rem; font-weight: 600;">{{ model.stats.transactions_count }}</div>
          </div>
          <div>
            <span style="color: var(--muted); font-size: 0.75rem;">Matched</span>
            <div style="font-size: 1.1rem; font-weight: 600; color: #0a0;">{{ model.stats.matched_count }}</div>
          </div>
          <div>
            <span style="color: var(--muted); font-size: 0.75rem;">Unmatched</span>
            <div style="font-size: 1.1rem; font-weight: 600; color: #c60;">{{ model.stats.unmatched_count }}</div>
          </div>
          <div>
            <span style="color: var(--muted); font-size: 0.75rem;">Time</span>
            <div style="font-size: 1.1rem; font-weight: 600;">{{ model.stats.elapsed_seconds?.toFixed(2) }}s</div>
          </div>
        </div>

        <div v-if="model.running" style="padding: 20px; text-align: center; color: var(--muted);">
          Running classification...
        </div>

        <div v-else-if="model.logs.length > 0" style="max-height: 300px; overflow-y: auto; font-family: 'SF Mono', Monaco, Consolas, monospace; font-size: 12px; line-height: 1.6; background: #1a1a1a; color: #ccc; padding: 12px; border-radius: 6px;">
          <div
            v-for="(log, index) in model.logs"
            :key="index"
            :style="{
              color: log.level === 'error' ? '#f66' : log.level === 'warning' ? '#fc6' : log.level === 'debug' ? '#888' : '#ccc',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word'
            }">
            <span style="opacity: 0.5;">[{{ log.level.toUpperCase().padEnd(5) }}]</span> {{ log.message }}
          </div>
        </div>

        <div v-else style="padding: 20px; text-align: center; color: var(--muted); font-size: 0.85rem;">
          Save rules or click "Run Classification" to see results
        </div>
      </div>
    </div>
  `,
};
