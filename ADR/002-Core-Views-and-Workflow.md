# ADR-002: Core Views and Workflow

## Status
Draft

## Context

Penny needs a clear user workflow that guides non-technical users from raw bank data to actionable financial insights. The data source reality is that we don't have proper banking APIs - instead we have historic CSV files downloaded at irregular intervals with potential overlaps.

## Taget Auidience

- Proficient non-technical users. Happy to download CSV files. 
- Good in Excel. Never used a programming tool.

## Value Proposition

- 

## Design Principles

### What Penny Is
- A **viewing and budgeting app** for personal finance
- Consolidates CSV exports into a unified transaction view
- Provides classification, reporting, and budget tracking

### What Penny Is Not
- **Not a storage system** - users must backup their original CSV files
- **Not a bookkeeping app** - no data entry, no manual transaction creation
- **Not a bank sync tool** - no API integrations, CSV-only

### Data Philosophy
- **Best effort persistence** - SQLite in app folder, no guarantees
- **Tombstone deletion** - "deleted" data is hidden, never truly removed
- **No data correction UI** - if e.g. deduplication, or CSV parsing does not work, this is a bug to be fixed by the developer. 


## Navigation Model

**Tabs, not a wizard.** The workflow describes a logical progression, but users can navigate freely between views at any time. Importing new CSVs doesn't reset the flow - new transactions appear in existing views automatically.

```
┌─────────────────────────────────────────────────────────────┐
│  [Import]  [Accounts]  [Transactions]  [Rules]  [Reports]   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                     Active View Content                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## View Specifications

### 1. Import View

**Purpose:** Entry point for getting bank data into Penny.

**User Interaction:**
- Drag & drop zone for CSV files
- Support multiple files from different banks
- Files may have overlapping date ranges (deduplication handled internally)

**CSV Format Discovery:**
- Dispatch on headers - library-shaped problem
- Detect bank from CSV structure (column names, format patterns)
- Leverage existing libraries where possible

**Account Identity Resolution:**
- Primary signal: IBAN from CSV header
- Secondary: Bank type from format discovery
- If ambiguous: prompt user or infer from import history
- File name is NOT a reliable signal

**UI Elements:**
- Drop zone with visual feedback
- Import progress spinner
- Warning/error messages for:
  - Unrecognized CSV formats
  - Parsing errors
- Import history/log

### 2. Accounts View

**Purpose:** Overview of all detected bank accounts.

**Data Model - Account:**
| Field | Description | Source |
|-------|-------------|--------|
| Bank Institute | e.g., "Comdirect" | Inferred from CSV format |
| Account Holder | Owner name(s) | CSV header |
| Account ID | IBAN or account number | CSV header |
| Account Type | Giro, Credit Card, Savings (Tagesgeld) | Inferred |
| Latest Balance | Most recent known balance | CSV header (date-specific) |
| Balance Date | When the balance was recorded | CSV header |
| Import Age | Time since last CSV import | Computed |
| Status | Active / Hidden (tombstone) | User-controlled |

**UI Elements:**
- Card-style layout (one card per account)
- Account icon/badge by type
- Balance display (prominent, with "as of" date)
- "Last updated X days ago" indicator
- Controls:
  - Hide account (tombstone - removes from all views)
  - View account details/transactions

**Scope:**
- Cash-valued accounts only (Giro, Credit Card, Savings)
- Stock portfolios excluded for v1
- Sub-accounts (e.g., Giro + Visa + Tagesgeld from same bank) shown as separate cards

**Balance Handling:**
- Extract from CSV header when available
- Show "Unknown" gracefully when not available
- Future: compute running balance from transactions (not v1)

### 3. Transactions View

**Purpose:** Consolidated list of all transactions across all accounts.

**UI Elements:**
- Table/list view with columns:
  - Date
  - Account (source)
  - Description/Reference
  - Amount
  - Category (from classification)
- Filtering:
  - By date range
  - By account
  - By category
  - By amount range
  - Text search
- Sorting by any column
- Pagination or virtual scrolling for large datasets

**Data Flow:**
- Aggregates transactions from all imported CSVs
- Automatic deduplication (same-bank overlapping imports)
- Classification column populated by rules engine
- Hidden accounts excluded

### 4. Classification Rules View

**Purpose:** Gmail filter-style UI for categorizing transactions.

**Reference UI:** Gmail Filters - proven, familiar pattern.

**Concept:**
- Rules match transactions based on conditions
- Each rule assigns a category from taxonomy
- Rules have priority order (first match wins)
- Manual override per-transaction supported

**Rule Structure:**
```
IF <conditions> THEN category = <category>
```

**Condition Types:**
- Description contains/matches (regex)
- Amount range
- Account
- Counterparty/IBAN

**UI Elements:**
- List of rules with:
  - Condition summary
  - Assigned category
  - Match count (how many transactions)
  - Enable/disable toggle
  - Edit/delete actions
- "Add Rule" button
- Rule editor modal/panel
- Test rule against transactions
- Drag-and-drop reordering (priority)

**Category Taxonomy:**
- Predefined starter categories
- User can add custom categories
- Hierarchical (e.g., Food > Groceries, Food > Restaurants)

**Integration:**
- Adds "Category" column to Transactions View
- Unclassified transactions shown with empty/default category
- Manual override: user can set category directly on transaction (overrides rules)

**Details:** See ADR-003 (Classification Rules) for full specification.

### 5. Finance Report View

**Purpose:** Visual financial analysis dashboard.

**Based on:** Existing FinanceAnalysis HTML report.

**Features:**
- Income vs. Expense summary
- Category breakdown (pie/bar charts)
- Time series (monthly/weekly spending)
- Sankey cash-flow diagram
- Top merchants/payees
- Configurable date range

### 6. Budget View (v2)

**Purpose:** Set and track spending budgets.

**Budget Definition:**
- Per expense category
- Time granularity: Annual / Monthly / Weekly
- Target amount

**UI Elements:**
- Budget cards per category
- Progress bars (spent vs. budget)
- Period selector (this month, this year, custom)
- Alerts for over-budget categories
- Historical tracking (how did we do last month?)

**Deferred to v2.**
