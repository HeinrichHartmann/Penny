/**
 * DateFilterPanel component for date range selection.
 */
import { MONTH_BUTTONS } from '../utils/date.js';

export const DateFilterPanel = {
  name: 'DateFilterPanel',
  props: {
    state: { type: Object, required: true },
    actions: { type: Object, required: true },
  },
  setup() {
    return {
      monthButtons: MONTH_BUTTONS,
    };
  },
  template: `
    <div class="selector-date-panel">
      <div class="selector-date-row">
        <div class="selector-date-shortcuts">
          <div class="btn-group wrap" style="gap: 6px;">
            <button v-for="y in state.yearButtons.slice().reverse().slice(0, 3)" :key="y" @click="actions.setYear(y)"
              :class="['shortcut-btn', actions.isActiveYear(y) ? 'active' : '']"
              style="min-width: 60px;">
              {{ y }}
            </button>
            <button @click="actions.setAll()"
              :class="['shortcut-btn', state.filters.from === state.meta.min_date && state.filters.to === state.meta.max_date ? 'active' : '']"
              style="min-width: 60px;">
              All
            </button>
          </div>
          <div class="btn-group wrap" style="gap: 4px;">
            <button v-for="m in monthButtons" :key="m.value" @click="actions.setMonth($event, m.value)"
              :disabled="state.monthShortcutYear === null"
              :class="['shortcut-btn', actions.isActiveMonth(m.value) ? 'active' : '']"
              style="min-width: 42px; font-size: 0.8rem;">
              {{ m.label }}
            </button>
            <button @click="actions.setYearAllMonths()"
              :class="['shortcut-btn', state.monthShortcutYear !== null && state.filters.from === state.monthShortcutYear+'-01-01' && state.filters.to === state.monthShortcutYear+'-12-31' ? 'active' : '']"
              style="min-width: 42px; font-size: 0.8rem;">
              All
            </button>
          </div>
        </div>

        <div class="selector-date-picker-row">
          <input type="date" class="date-input" :value="state.filters.from" @input="actions.updateFrom($event.target.value)">
          <span class="selector-date-arrow">→</span>
          <input type="date" class="date-input" :value="state.filters.to" @input="actions.updateTo($event.target.value)">
        </div>
      </div>
    </div>
  `,
};
