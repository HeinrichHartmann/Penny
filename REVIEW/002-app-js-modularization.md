# app.js Modularization Proposal

## Problem

`app.js` is 917 lines handling all application concerns in a single `setup()` function. The code is organized by concern type (state, watchers, methods) rather than by feature, making it hard to navigate and maintain.

## Approach: View-Centric Modules

Split by **what the user sees**, not by technical concern. Each sidebar item becomes a self-contained view module. Shared UI becomes components. Pure logic stays in utils.

Avoid "helper kitchen sink" files. If shared logic accumulates, it's a sign of unclear abstractions.

---

## Proposed Structure

```
static/
├── app.js                      # Shell: sidebar + routing + shared state
│
├── views/
│   ├── ImportView.js           # Self-contained
│   ├── AccountsView.js         # Self-contained
│   ├── RulesView.js            # Self-contained
│   ├── TransactionsView.js     # Uses SelectorHeader
│   ├── ReportView.js           # Uses SelectorHeader + charts
│   └── SettingsView.js         # Self-contained
│
├── components/
│   ├── Sidebar.js              # Navigation menu
│   ├── SelectorHeader.js       # Shared filter UI (exists)
│   ├── DateFilterPanel.js      # Date picker (exists)
│   └── Pagination.js           # Reusable pagination
│
├── charts.js                   # ECharts wrappers (exists)
│
└── utils/
    ├── format.js               # formatCurrency, toMarkdownTable (exists)
    ├── date.js                 # Date math (exists)
    └── color.js                # Palette (exists)
```

---

## Layer Responsibilities

| Layer | Owns | Fetches Data? | Has State? |
|-------|------|---------------|------------|
| **app.js** | Routing, shared filters | Yes (meta on init) | Minimal |
| **views/** | Everything for that screen | Yes, directly | Yes, local |
| **components/** | Reusable UI | No | Props in, events out |
| **utils/** | Pure transformations | No | No |

---

## Shared State

Only state that's legitimately used by multiple views lives in `app.js`:

| State | Used By | Why Shared |
|-------|---------|------------|
| `view` | Sidebar, routing | Navigation |
| `meta` | SelectorHeader | Account list, date bounds |
| `filters` | Transactions, Report | Same filter controls |
| `selectedCategory` | Transactions, Report | Drill-down persists across views |
| `searchQuery` | Transactions, Report | Search persists across views |

Everything else is view-local.

---

## View Specifications

### `app.js` (~150 lines)

**Owns:** View routing, shared state, URL sync.

```javascript
createApp({
  components: { Sidebar, ImportView, AccountsView, ... },
  setup() {
    const view = ref('report');
    const meta = reactive({ accounts: [], min_date: '', max_date: '' });
    const filters = reactive({ from: '', to: '', accounts: [], neutralize: true });
    const selectedCategory = ref(null);
    const searchQuery = ref('');

    // URL state sync
    // Meta initialization
    // Pass shared state to views as props

    return { view, meta, filters, selectedCategory, searchQuery, ... };
  }
});
```

**Template:**
```html
<Sidebar :view="view" @navigate="view = $event" />
<ImportView v-if="view === 'import'" @imported="refreshMeta" />
<AccountsView v-if="view === 'accounts'" :filters="filters" />
<TransactionsView v-if="view === 'transactions'"
  :filters="filters" :meta="meta"
  :selectedCategory="selectedCategory" :searchQuery="searchQuery" />
<!-- etc -->
```

---

### `views/ImportView.js` (~80 lines)

**Self-contained.** No shared state needed.

```javascript
export const ImportView = {
  emits: ['imported'],
  setup(props, { emit }) {
    const state = reactive({
      isDragging: false,
      isUploading: false,
      lastResult: null,
      error: null,
    });

    const handleDrop = async (event) => {
      // ... upload logic
      const resp = await fetch('/api/import', { method: 'POST', body: formData });
      state.lastResult = await resp.json();
      emit('imported');
    };

    return { state, handleDrop, handleDragOver, handleDragLeave, handleFileSelect };
  },
  template: `<!-- drop zone, results -->`,
};
```

---

### `views/AccountsView.js` (~70 lines)

**Self-contained.** Receives `filters` only for account toggle sync.

```javascript
export const AccountsView = {
  props: ['filters'],
  setup(props) {
    const accounts = ref([]);
    const loading = ref(false);
    const editingId = ref(null);
    const editingName = ref('');

    const load = async () => {
      loading.value = true;
      const resp = await fetch('/api/accounts');
      accounts.value = (await resp.json()).accounts;
      loading.value = false;
    };

    const saveName = async (id) => {
      await fetch(`/api/accounts/${id}?display_name=${editingName.value}`, { method: 'PATCH' });
      await load();
      editingId.value = null;
    };

    onMounted(load);

    return { accounts, loading, editingId, editingName, load, saveName, ... };
  },
  template: `<!-- account cards grid -->`,
};
```

---

### `views/RulesView.js` (~90 lines)

**Self-contained.** No shared state needed.

```javascript
export const RulesView = {
  setup() {
    const state = reactive({
      path: '',
      content: '',
      originalContent: '',
      loading: false,
      saving: false,
      running: false,
      error: null,
      logs: [],
      stats: null,
    });

    const hasChanges = computed(() => state.content !== state.originalContent);

    const load = async () => {
      state.loading = true;
      const data = await fetch('/api/rules').then(r => r.json());
      state.path = data.path;
      state.content = data.content || '';
      state.originalContent = state.content;
      state.loading = false;
    };

    const save = async () => {
      state.saving = true;
      await fetch('/api/rules', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: state.content }),
      });
      state.originalContent = state.content;
      await runClassification();
      state.saving = false;
    };

    onMounted(load);

    return { state, hasChanges, load, save, runClassification };
  },
  template: `<!-- editor, logs panel -->`,
};
```

---

### `views/TransactionsView.js` (~120 lines)

**Receives shared state.** Owns table logic.

```javascript
export const TransactionsView = {
  components: { SelectorHeader, Pagination },
  props: ['filters', 'meta', 'selectedCategory', 'searchQuery'],
  emits: ['update:selectedCategory', 'update:searchQuery'],
  setup(props, { emit }) {
    const transactions = ref(null);
    const currentPage = ref(1);
    const sort = reactive({ key: 'booking_date', direction: 'desc' });

    const load = async () => {
      const params = new URLSearchParams();
      params.set('from', props.filters.from);
      params.set('to', props.filters.to);
      params.set('accounts', props.filters.accounts.join(','));
      if (props.selectedCategory) params.set('category', props.selectedCategory);
      if (props.searchQuery) params.set('q', props.searchQuery);

      const resp = await fetch(`/api/transactions?${params}`);
      transactions.value = await resp.json();
    };

    const sortedTransactions = computed(() => { /* sort logic */ });
    const visibleTransactions = computed(() => { /* pagination */ });

    watch(() => [props.filters, props.selectedCategory, props.searchQuery], load, { deep: true });
    onMounted(load);

    return { transactions, sortedTransactions, visibleTransactions, currentPage, sort, ... };
  },
  template: `<!-- SelectorHeader + table + Pagination -->`,
};
```

---

### `views/ReportView.js` (~200 lines)

**Receives shared state.** Owns charts, tabs, report data.

```javascript
export const ReportView = {
  components: { SelectorHeader },
  props: ['filters', 'meta', 'selectedCategory', 'searchQuery'],
  emits: ['update:selectedCategory', 'update:searchQuery'],
  setup(props, { emit }) {
    const tab = ref('expense');
    const summary = ref(null);
    const tree = ref(null);
    const pivot = ref(null);
    const cashflow = ref(null);
    const breakout = ref(null);
    const reportText = ref('');

    const pivotDepth = ref('1');
    const breakoutGranularity = ref('auto');
    const breakoutShowIncome = ref(true);
    const breakoutShowExpenses = ref(true);

    // Chart refs
    const treemapEl = ref(null);
    const sankeyEl = ref(null);
    const breakoutEl = ref(null);

    // Use existing charts.js
    const charts = createChartManager({ treemapEl, sankeyEl, breakoutEl, ... });

    const loadSummary = async () => { /* fetch /api/summary */ };
    const loadTree = async () => { /* fetch /api/tree */ };
    const loadPivot = async () => { /* fetch /api/pivot */ };
    // ... etc

    const loadAll = async () => {
      await loadSummary();
      if (tab.value === 'expense' || tab.value === 'income') {
        await Promise.all([loadTree(), loadPivot()]);
      } else if (tab.value === 'cashflow') {
        await loadCashflow();
      }
      // ...
    };

    watch(() => [props.filters, props.selectedCategory, tab.value], loadAll, { deep: true });
    onMounted(loadAll);

    return { tab, summary, tree, pivot, ..., treemapEl, sankeyEl, ... };
  },
  template: `<!-- SelectorHeader + summary cards + tabs + charts + pivot -->`,
};
```

---

### `views/SettingsView.js` (~30 lines)

**Self-contained.** Minimal.

```javascript
export const SettingsView = {
  props: ['filters'],
  template: `
    <div class="panel">
      <h3>Data Processing</h3>
      <label>
        <input type="checkbox" v-model="filters.neutralize">
        Neutralize transfers
      </label>
    </div>
  `,
};
```

---

## Components

### `components/Sidebar.js` (~50 lines)

Extract navigation from `index.html`. Pure UI.

```javascript
export const Sidebar = {
  props: ['view'],
  emits: ['navigate'],
  template: `
    <aside class="sidebar">
      <nav class="sidebar-nav">
        <h1 class="sidebar-title">Penny</h1>
        <button v-for="item in items"
          :class="['nav-item', view === item.id ? 'active' : '']"
          @click="$emit('navigate', item.id)">
          <span class="nav-icon"><!-- svg --></span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>
    </aside>
  `,
  setup() {
    const items = [
      { id: 'import', label: 'Import' },
      { id: 'accounts', label: 'Accounts' },
      { id: 'rules', label: 'Rules' },
      { id: 'transactions', label: 'Transactions' },
      { id: 'report', label: 'Report' },
    ];
    return { items };
  },
};
```

### `components/Pagination.js` (~40 lines)

Extract from TransactionsView. Reusable.

```javascript
export const Pagination = {
  props: ['currentPage', 'totalPages'],
  emits: ['update:currentPage'],
  // ... page buttons, prev/next
};
```

---

## Data Fetching

**Views fetch directly.** No abstraction layer.

```javascript
// In RulesView.js
const resp = await fetch('/api/rules');
const data = await resp.json();
```

**Delete `api.js`?**

The current `api.js` has two parts:
1. Simple fetch wrappers (`fetchRules`, `saveRules`) - can inline into views
2. `createApi()` factory - complex, tightly coupled to current structure

**Recommendation:** Inline the simple fetches. Delete `createApi()`. If URL building becomes repetitive, add a small `buildQueryString()` utility.

---

## Migration Plan

### Phase 1: Extract Self-Contained Views
1. `ImportView.js` - no dependencies
2. `AccountsView.js` - no dependencies
3. `RulesView.js` - no dependencies
4. `SettingsView.js` - trivial

### Phase 2: Extract Shared Components
1. `Sidebar.js` - from index.html
2. `Pagination.js` - from transaction table logic

### Phase 3: Extract Complex Views
1. `TransactionsView.js` - uses SelectorHeader, Pagination
2. `ReportView.js` - uses SelectorHeader, charts

### Phase 4: Slim Down app.js
1. Remove inlined view logic
2. Keep only: routing, shared state, URL sync
3. Delete `createApi()` from api.js

---

## File Size Estimates

| File | Lines | Change |
|------|-------|--------|
| `app.js` | ~150 | From 917 |
| `views/ImportView.js` | ~80 | New |
| `views/AccountsView.js` | ~70 | New |
| `views/RulesView.js` | ~90 | New |
| `views/TransactionsView.js` | ~120 | New |
| `views/ReportView.js` | ~200 | New |
| `views/SettingsView.js` | ~30 | New |
| `components/Sidebar.js` | ~50 | New |
| `components/Pagination.js` | ~40 | New |
| `api.js` | ~50 | From 328 (or delete) |

**Total:** ~880 lines across 10 files vs 917 in 1 file.

---

## Principles

1. **Views own their data.** Each view fetches from `/api/...` directly.
2. **Shared state is explicit.** Only filters/meta passed as props.
3. **Components are pure UI.** Props in, events out, no fetch.
4. **Utils are pure functions.** No state, no side effects.
5. **No helper kitchen sinks.** If shared logic grows, rethink the abstraction.
