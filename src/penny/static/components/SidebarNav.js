const PRIMARY_ITEMS = [
  {
    id: 'import',
    label: 'Import',
    icon: '<path d="M8 2v8"></path><path d="M5 7.5 8 10.5 11 7.5"></path><path d="M3 12.5h10"></path>',
  },
  {
    id: 'accounts',
    label: 'Accounts',
    icon: '<rect x="2.5" y="4" width="11" height="8" rx="1.5"></rect><path d="M10.5 8h3"></path><path d="M4.5 6.5h3"></path>',
  },
  {
    id: 'rules',
    label: 'Rules',
    icon: '<path d="M3 4.5h10"></path><path d="M3 8h10"></path><path d="M3 11.5h10"></path><circle cx="6" cy="4.5" r="1"></circle><circle cx="10" cy="8" r="1"></circle><circle cx="7" cy="11.5" r="1"></circle>',
  },
  {
    id: 'transactions',
    label: 'Transactions',
    icon: '<path d="M4 4.5h9"></path><path d="M4 8h9"></path><path d="M4 11.5h9"></path><path d="M2.5 4.5h.01"></path><path d="M2.5 8h.01"></path><path d="M2.5 11.5h.01"></path>',
  },
  {
    id: 'report',
    label: 'Report',
    icon: '<path d="M3 12.5h10"></path><path d="M5 12.5v-3"></path><path d="M8 12.5v-6"></path><path d="M11 12.5v-4.5"></path>',
  },
  {
    id: 'balance',
    label: 'Balance',
    icon: '<path d="M2.5 8h11"></path><path d="M3 4l5 4 5-4"></path><path d="M3 12l5-4 5 4"></path><circle cx="8" cy="8" r="1"></circle>',
  },
];

const FOOTER_ITEMS = [
  {
    id: 'settings',
    label: 'Settings',
    icon: '<circle cx="8" cy="8" r="2.2"></circle><path d="M8 2.5v1.3"></path><path d="M8 12.2v1.3"></path><path d="M13.5 8h-1.3"></path><path d="M3.8 8H2.5"></path><path d="m11.9 4.1-.9.9"></path><path d="m5 11-.9.9"></path><path d="m11.9 11.9-.9-.9"></path><path d="m5 5-.9-.9"></path>',
  },
];

export const SidebarNav = {
  name: 'SidebarNav',
  emits: ['navigate'],
  props: {
    view: { type: String, required: true },
  },
  setup() {
    return {
      primaryItems: PRIMARY_ITEMS,
      footerItems: FOOTER_ITEMS,
    };
  },
  template: `
    <aside class="sidebar">
      <nav class="sidebar-nav">
        <h1 class="sidebar-title">Penny</h1>
        <button
          v-for="item in primaryItems"
          :key="item.id"
          @click="$emit('navigate', item.id)"
          :class="['nav-item', view === item.id ? 'active' : '']"
        >
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 16 16" v-html="item.icon"></svg>
          </span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>
      <nav class="sidebar-footer">
        <button
          v-for="item in footerItems"
          :key="item.id"
          @click="$emit('navigate', item.id)"
          :class="['nav-item', view === item.id ? 'active' : '']"
        >
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 16 16" v-html="item.icon"></svg>
          </span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>
    </aside>
  `,
};
