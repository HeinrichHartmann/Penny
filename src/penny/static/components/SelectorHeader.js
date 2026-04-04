/**
 * Shared selector header for report and transactions views.
 */
import { DateFilterPanel } from './DateFilterPanel.js';

export const SelectorHeader = {
  name: 'SelectorHeader',
  components: {
    DateFilterPanel,
  },
  props: {
    state: { type: Object, required: true },
    actions: { type: Object, required: true },
  },
  template: `
    <div class="panel selector-header">
      <div class="selector-grid">
        <section class="selector-block selector-block-dates">
          <div class="selector-label">Dates</div>
          <date-filter-panel
            :state="state"
            :actions="actions"
          />
        </section>

        <section class="selector-block">
          <div class="selector-label">Accounts</div>
          <div class="selector-account-list">
            <button
              v-for="acc in state.meta.accounts"
              :key="acc.id"
              type="button"
              @click="actions.toggleAccount(acc.id)"
              :class="['selector-account-chip', state.filters.accounts.includes(acc.id) ? 'active' : '']"
            >
              <span class="selector-account-icon" aria-hidden="true">
                <svg viewBox="0 0 16 16">
                  <rect x="2.5" y="4" width="11" height="8" rx="1.5"></rect>
                  <path d="M10.5 8h3"></path>
                  <path d="M4.5 6.5h3"></path>
                </svg>
              </span>
              <span class="selector-account-name">{{ acc.label }}</span>
            </button>
          </div>
        </section>

        <section class="selector-block">
          <div class="selector-label">Category</div>
          <div class="selector-category-stack">
            <div class="category-breadcrumb compact selector-category-breadcrumb">
              <button
                type="button"
                @click="actions.clearSelection()"
                :class="['breadcrumb-link', !state.selectedCategory ? 'active' : '']"
              >
                All Categories
              </button>
              <template v-for="crumb in state.categoryBreadcrumbs" :key="crumb.path">
                <span class="breadcrumb-sep">/</span>
                <button
                  type="button"
                  @click="actions.applyCategorySelection(crumb.path)"
                  :class="['breadcrumb-link', state.selectedCategory === crumb.path ? 'active' : '']"
                >
                  {{ crumb.label }}
                </button>
              </template>
            </div>
            <div class="selector-inline-row">
              <select
                class="search-input selector-select"
                :value="state.categorySelectValue"
                @change="actions.updateCategorySelectValue($event.target.value); actions.applyCategorySelection($event.target.value || null)"
                :disabled="state.nextCategoryOptions.length === 0"
              >
                <option value="">
                  {{ state.nextCategoryOptions.length === 0
                    ? 'No narrower categories'
                    : state.selectedCategory
                      ? 'Choose next level'
                      : 'Choose category' }}
                </option>
                <option
                  v-for="option in state.nextCategoryOptions"
                  :key="option.path"
                  :value="option.path"
                >
                  {{ option.label }}
                </option>
              </select>
              <button v-if="state.selectedCategory" type="button" class="shortcut-btn" @click="actions.clearSelection()">Clear</button>
            </div>
          </div>
        </section>

        <section class="selector-block">
          <div class="selector-label">Search</div>
          <input
            class="search-input selector-wide-input"
            type="text"
            :value="state.searchQuery"
            @input="actions.updateSearchQuery($event.target.value)"
            placeholder="Search description"
          >
        </section>
      </div>
    </div>
  `,
};
