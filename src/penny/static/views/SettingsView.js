export const SettingsView = {
  name: 'SettingsView',
  props: {
    filters: { type: Object, required: true },
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Settings</h2>

      <div class="panel" style="padding: 24px;">
        <h3 style="font-size: 1rem; font-weight: 600; margin-bottom: 16px; color: var(--ink);">Data Processing</h3>

        <label style="display: flex; align-items: center; gap: 12px; cursor: pointer; padding: 12px 0;">
          <input type="checkbox" v-model="filters.neutralize" style="width: 18px; height: 18px; cursor: pointer;">
          <div>
            <div style="font-size: 0.9rem; font-weight: 500;">Neutralize transfers</div>
            <div style="font-size: 0.8rem; color: var(--muted); margin-top: 2px;">
              Automatically hide internal transfers between your accounts to avoid double-counting
            </div>
          </div>
        </label>
      </div>
    </div>
  `,
};
