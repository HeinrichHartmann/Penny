# ADR-002: Product Positioning and Core Views

## Status
Draft

---

# Part 1: Product Positioning and Design Principles

## What Penny Is

Penny is **open source infrastructure for LLM-assisted personal finance**.

- Self-hosted, installable application (macOS DMG)
- Privacy-first: all data stays on your machine
- CSV-based import with plugin architecture
- LLM-friendly data formats for collaborative rule authoring
- A viewer and dashboard - the intelligence lives in the human + LLM collaboration

## What Penny Is Not

- **Not a SaaS finance app** - no cloud, no subscription, no data sharing
- **Not competing with YNAB/Mint** - different category entirely
- **Not a bank sync tool** - deliberately CSV-only (see rationale below)
- **Not a bookkeeping app** - no manual transaction entry
- **Not a storage system** - users backup their own CSV files

## Why CSV-Only: The Banking API Reality

"Why not just sync with the bank?"

| Approach | Reality |
|----------|---------|
| **FinTS/HBCI** | Ancient XML APIs, bank-specific implementations, frequently breaking, many banks dropping support |
| **Sofortüberweisung/Klarna** | Credential sharing - requires your bank password |
| **PSD2 "Open Banking"** | Banks implemented bare minimum, mostly payment initiation, not data export |
| **finAPI, Plaid, Salt Edge** | Commercial SaaS - your data goes to their cloud |

There is no legal, self-hosted, open source, multi-bank sync solution that actually works.

CSV export is:
- Available from every bank
- Under user control
- Privacy-preserving
- Stable (formats rarely change)

The friction of manual CSV download is a **constraint of the problem space**, not a design flaw.

## Target Audience

**Primary:** Privacy-conscious users comfortable with CSV exports who want consolidated financial visibility.

**Realistic profile:**
- Financially literate (understands budgets, categories, cash flow)
- Willing to download CSV files monthly
- Comfortable with file management (drag & drop)
- May use LLM tools (Claude, ChatGPT) for assistance

**Not the target:** Users who expect automatic bank sync or zero-friction onboarding.

## Value Proposition

- **Multi-bank consolidation** - all accounts in one view, across banks, over years
- **Financial literacy** - understand household finances like an accountant
- **Privacy** - no credentials shared, no data leaves your machine
- **LLM-powered classification** - collaborate with AI to categorize transactions
- **Tax preparation** - export clean category breakdowns for accountants

## Design Principles

### Bank Support = Plugin Problem

Bank CSV parsing is a library problem, not an app problem.

```
penny-importers/
├── comdirect.py      # Maintainer
├── sparkasse.py      # Maintainer
├── ing_diba.py       # Community
├── n26.py            # Community
└── us_chase.py       # Community
```

- Small Python files (~200 lines each)
- Easy to write with LLM assistance
- Community-contributable via open source repo
- Users can drop custom parsers into a local folder

**Initial support:** Comdirect, Sparkasse, one US bank.

### Classification = LLM Collaboration Problem

Classification is not a UI problem - it's a collaboration problem.

**The workflow:**
```
1. Open Penny → Transactions view
2. Export top 50 unclassified as Markdown
3. Paste into Claude: "Write YAML classification rules for these"
4. Claude generates rules
5. Drop YAML into rules folder
6. Penny hot-reloads → transactions classified
7. Iterate
```

**Ship sensible defaults:**
- German groceries (REWE, EDEKA, Aldi, Lidl)
- Common merchants (Amazon, PayPal, DHL)
- Standard categories (Food, Transport, Housing, etc.)

But the power is in the iterative refinement loop with an LLM.

### CLI as First-Class Citizen

The `penny` CLI shares state with the GUI app:

```bash
penny import ~/Downloads/comdirect-export.csv
penny transactions --unclassified --limit 50 --format markdown
penny rules reload
penny report --month 2024-03
```

This enables:
- Claude Code can directly read transactions, write rules
- Scriptable workflows
- Power users get full control
- GUI is for viewing, CLI is for authoring

**Distribution:** CLI installable alongside DMG, or via `uv tool install`.

### LLM-Friendliness

Design for AI co-creation from the start:

- **Markdown exports** - every view has copy-to-clipboard as Markdown
- **YAML rules** - human-readable, LLM-writable classification rules on filesystem
- **Readable database** - SQLite with clear table/column names, useful views pre-defined
- **Hot reload** - edit rules externally, Penny picks up changes
- **MCP integration path** - architecture supports future Model Context Protocol server

### Data Philosophy

- **Best effort persistence** - SQLite in app folder, no guarantees
- **Tombstone deletion** - "deleted" data is hidden, never truly removed
- **No data correction UI** - parsing bugs are fixed in code, not worked around in UI
- **Source of truth** - original CSV files, not the database

---

# Part 2: Views and Workflow

## Success Criteria

**The project succeeds when:** A privacy-conscious, financially-literate user can perform monthly household financial review using Penny + an LLM for rule authoring.

## Use Cases

### Monthly Financial Review
Sit down monthly for household financial planning. Import latest CSVs, review categorized transactions, check reports.

### Tax Preparation
Generate clean rundowns of income and expenses by category. Export as Markdown or CSV for accountants.

### Budget Tracking (v2)
Set spending targets, track against them, identify overruns early.

## Navigation Model

**Tabs, not a wizard.** Users navigate freely between views. Importing new CSVs doesn't reset flow - new transactions appear automatically.

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

**Bank Detection:**
- Plugin system dispatches on headers/structure
- Each importer declares what patterns it recognizes
- Unrecognized formats show clear error with guidance

**Account Identity Resolution:**
- Primary signal: IBAN from CSV header
- Secondary: Bank type from format discovery
- If ambiguous: prompt user or infer from import history
- File name is NOT a reliable signal

**UI Elements:**
- Drop zone with visual feedback
- Import progress indicator
- Warning/error messages for parsing issues
- Import history/log
- "Export unrecognized sample" button (for community parser development)

### 2. Accounts View

**Purpose:** Overview of all detected bank accounts.

**Data Model - Account:**
| Field | Description | Source |
|-------|-------------|--------|
| Bank Institute | e.g., "Comdirect" | Inferred from CSV format |
| Account Holder | Owner name(s) | CSV header |
| Account ID | IBAN or account number | CSV header |
| Account Type | Giro, Credit Card, Savings | Inferred |
| Latest Balance | Most recent known balance | CSV header |
| Balance Date | When balance was recorded | CSV header |
| Import Age | Time since last CSV import | Computed |
| Status | Active / Hidden | User-controlled |

**UI Elements:**
- Card-style layout (one card per account)
- Balance display with "as of" date
- "Last updated X days ago" indicator
- Hide account action (tombstone)

**Scope:**
- Cash-valued accounts only (Giro, Credit Card, Savings)
- Stock portfolios excluded for v1

### 3. Transactions View

**Purpose:** Consolidated list of all transactions across all accounts.

**UI Elements:**
- Table with columns: Date, Account, Description, Amount, Category
- Filtering: date range, account, category, amount range, text search
- Sorting by any column
- Pagination or virtual scrolling

**Key Feature: Markdown Export**
- "Copy as Markdown" button
- Exports filtered/selected transactions
- Designed for pasting into LLM conversations
- Includes column headers, aligned formatting

**Data Flow:**
- Aggregates transactions from all imported CSVs
- Automatic deduplication
- Classification populated by rules engine
- Hidden accounts excluded

### 4. Rules View

**Purpose:** View and manage classification rules.

**Primary workflow:** Rules are authored externally (text editor, Claude Code) and hot-reloaded.

**UI provides:**
- List of active rules with match counts
- Enable/disable toggle per rule
- "Open rules folder" button
- "Reload rules" button
- Validation errors displayed clearly

**Rule format:** YAML files in rules folder (see ADR-003).

**Starter rules:** Ship with defaults for common merchants:
- German groceries: REWE, EDEKA, Aldi, Lidl, dm, Rossmann
- Online: Amazon, PayPal, eBay
- Transport: Deutsche Bahn, Shell, Aral
- Subscriptions: Netflix, Spotify, Apple

**Category Taxonomy:**
- Hierarchical (e.g., Food > Groceries, Food > Restaurants)
- Predefined starter set
- User-extensible via YAML

### 5. Reports View

**Purpose:** Visual financial analysis dashboard.

**Based on:** Existing FinanceAnalysis HTML report.

**Features:**
- Income vs. Expense summary
- Category breakdown (pie/bar charts)
- Time series (monthly/weekly spending)
- Sankey cash-flow diagram
- Top merchants/payees
- Configurable date range

**Export:** "Copy as Markdown" for sharing with LLMs or others.

### 6. Budget View (v2)

**Deferred to v2.**

**Planned:**
- Budget targets per expense category
- Progress tracking (spent vs. budget)
- Period selector (month, year, custom)
- Over-budget alerts

---

## Open Items

- [ ] ADR-003: Classification Rules format specification
- [ ] Define penny-importers plugin API
- [ ] CLI command specification
