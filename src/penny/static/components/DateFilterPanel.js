/**
 * DateFilterPanel component for date range selection.
 */
import { MONTH_BUTTONS } from '../utils/date.js';

export const DateFilterPanel = {
  name: 'DateFilterPanel',
  props: {
    filters: { type: Object, required: true },
    meta: { type: Object, required: true },
    yearButtons: { type: Array, required: true },
    monthShortcutYear: { type: Number, default: null },
    setYear: { type: Function, required: true },
    setAll: { type: Function, required: true },
    setMonth: { type: Function, required: true },
    setYearAllMonths: { type: Function, required: true },
    isActiveYear: { type: Function, required: true },
    isActiveMonth: { type: Function, required: true },
  },
  setup() {
    return {
      monthButtons: MONTH_BUTTONS,
    };
  },
  template: `
    <div class="panel" style="margin-bottom: 20px; padding: 20px 24px;">
      <div style="display: flex; gap: 32px; align-items: start; flex-wrap: wrap;">

        <!-- Range Shortcuts -->
        <div style="flex: 1; min-width: 320px;">
          <label class="group-label" style="font-size: 0.85rem; font-weight: 500; margin-bottom: 10px; display: block;">Range</label>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <!-- Row 1: Years + All -->
            <div class="btn-group wrap" style="gap: 6px;">
              <button v-for="y in yearButtons.slice().reverse().slice(0, 3)" :key="y" @click="setYear(y)"
                :class="['shortcut-btn', isActiveYear(y) ? 'active' : '']"
                style="min-width: 60px;">
                {{ y }}
              </button>
              <button @click="setAll()"
                :class="['shortcut-btn', filters.from === meta.min_date && filters.to === meta.max_date ? 'active' : '']"
                style="min-width: 60px;">
                All
              </button>
            </div>
            <!-- Row 2: Months -->
            <div class="btn-group wrap" style="gap: 4px;">
              <button v-for="m in monthButtons" :key="m.value" @click="setMonth($event, m.value)"
                :disabled="monthShortcutYear === null"
                :class="['shortcut-btn', isActiveMonth(m.value) ? 'active' : '']"
                style="min-width: 42px; font-size: 0.8rem;">
                {{ m.label }}
              </button>
              <button @click="setYearAllMonths()"
                :class="['shortcut-btn', monthShortcutYear !== null && filters.from === monthShortcutYear+'-01-01' && filters.to === monthShortcutYear+'-12-31' ? 'active' : '']"
                style="min-width: 42px; font-size: 0.8rem;">
                All
              </button>
            </div>
          </div>
        </div>

        <!-- Custom Date Pickers -->
        <div style="display: flex; flex-direction: column; gap: 10px;">
          <label class="group-label" style="font-size: 0.85rem; font-weight: 500;">Custom Range</label>
          <div style="display: flex; gap: 10px; align-items: center;">
            <div>
              <label style="font-size: 0.75rem; color: var(--muted); display: block; margin-bottom: 4px;">From</label>
              <input type="date" :value="filters.from" @input="$emit('update:from', $event.target.value)" style="font-size: 0.85rem;">
            </div>
            <div style="color: var(--muted); padding-top: 18px;">→</div>
            <div>
              <label style="font-size: 0.75rem; color: var(--muted); display: block; margin-bottom: 4px;">To</label>
              <input type="date" :value="filters.to" @input="$emit('update:to', $event.target.value)" style="font-size: 0.85rem;">
            </div>
          </div>
          <div style="font-size: 0.75rem; color: var(--muted);">
            {{ filters.from }} to {{ filters.to }}
          </div>
        </div>

      </div>
    </div>
  `,
  emits: ['update:from', 'update:to'],
};
