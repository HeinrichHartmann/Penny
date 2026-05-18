/**
 * Right-aligned control bar for tabs that show breakout-style data.
 * Encapsulates income/expense toggles and granularity selector.
 *
 * state:   { granularityMode, showIncome, showExpenses }
 * actions: { setGranularityMode, setShowIncome, setShowExpenses }
 *
 * Slots:
 *   default  — extra controls inserted before the granularity buttons
 *   #right   — extra controls inserted after the granularity buttons
 */
export const BreakoutSelector = {
  name: 'BreakoutSelector',
  props: {
    state: { type: Object, required: true },
    actions: { type: Object, required: true },
  },
  template: `
    <div class="breakout-selector">
      <div class="check-group">
        <label>
          <input type="checkbox" :checked="state.showIncome"
            @change="actions.setShowIncome($event.target.checked)">
          Income
        </label>
        <label>
          <input type="checkbox" :checked="state.showExpenses"
            @change="actions.setShowExpenses($event.target.checked)">
          Expenses
        </label>
      </div>
      <slot></slot>
      <div class="btn-group wrap">
        <button v-for="m in ['auto','month','week','day']" :key="m"
          @click="actions.setGranularityMode(m)"
          :class="['shortcut-btn', state.granularityMode === m ? 'active' : '']">
          {{ {auto:'Auto', month:'Month', week:'Week', day:'Day'}[m] }}
        </button>
      </div>
      <slot name="right"></slot>
    </div>
  `,
};
