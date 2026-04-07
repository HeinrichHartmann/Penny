# Penny

Local-first personal finance built on your bank's original records.

Download your bank's CSV exports, drop them into Penny unchanged, and get trustworthy financial reports. All data stays on your machine. No cloud sync, no credential sharing, no black boxes.

<p align="center">
  <img src="docs/screenshots/report-expense.png" width="80%" alt="Penny - Expense Report" />
</p>

## Install

**Desktop App:** Download the latest DMG from [GitHub Releases](https://github.com/HeinrichHartmann/Penny/releases).

**CLI:** `uv tool install git+https://github.com/HeinrichHartmann/Penny.git`

The CLI enables LLM-assisted workflows for power users. The desktop app is the primary interface.

## How It Works

Penny is built around a simple workflow:

1. **Download** your bank's official CSV exports (monthly, quarterly, or whenever you want to review)
2. **Drop** them into Penny unchanged—no manual cleanup, no preprocessing
3. **Archive** - Penny preserves the original files as your source of truth
4. **Classify** - Apply Python rules to categorize transactions (co-create rules with Claude or other LLMs)
5. **Review** - Explore consolidated accounts, transactions, and reports across all your banks

The database is a derived projection—you can rebuild it from your archived imports at any time. This means you have a complete, auditable financial archive that's not locked into any vendor's format.

## Views

<p align="center">
  <img src="docs/screenshots/import.png" width="45%" alt="Import" />
  <img src="docs/screenshots/accounts.png" width="45%" alt="Accounts" />
</p>
<p align="center">
  <em>Import bank CSVs unchanged</em> · <em>Manage accounts and balance anchors</em>
</p>

**Import** is your entry point. Drag and drop CSV files from any supported bank. Penny detects the format, parses it, and archives the original file. The import history shows what you've loaded and when.

**Accounts** shows all your accounts across banks in one place. Record manual balance snapshots to create anchors—ground-truth reference points that help you verify transaction history is complete.

<p align="center">
  <img src="docs/screenshots/rules.png" width="45%" alt="Rules" />
  <img src="docs/screenshots/transactions.png" width="45%" alt="Transactions" />
</p>
<p align="center">
  <em>Python classification rules</em> · <em>Filter and search transactions</em>
</p>

**Rules** are how you categorize transactions. Write Python rules that match transaction descriptions and assign categories. The rules editor shows match statistics and lets you test changes interactively. Co-create rules with LLMs by exporting unclassified transactions as Markdown and asking your LLM to write rules.

**Transactions** gives you a consolidated, filterable view of everything across all accounts. Search by description, filter by date range or category, and track how your money moves.

<p align="center">
  <img src="docs/screenshots/report-cashflow.png" width="45%" alt="Cash Flow" />
  <img src="docs/screenshots/balance.png" width="45%" alt="Balance" />
</p>
<p align="center">
  <em>Cash flow Sankey diagram</em> · <em>Balance history with anchors</em>
</p>

**Reports** visualize your financial picture. See spending breakdowns by category with treemaps and pivot tables, cash flow with Sankey diagrams, and income summaries. Filter by date range and account.

**Balance** shows account balance history over time, with recorded balance anchors displayed as reference points. This helps you verify that your transaction history is complete and accurate.

## Features

### Privacy-First
All data stays on your machine. Penny never syncs to the cloud, never asks for bank credentials, and never sends your financial data anywhere. You control the files, the database, and the archive.

### Artifact-First Import
Drop your bank's official CSV exports unchanged. Penny archives the original files and parses them into a normalized database. If parsing logic improves, rebuild from the originals—your source of truth never changes.

### Rebuildable State
The SQLite database is a derived projection, not the source of truth. Archive imports are the foundation. Rebuild the database at any time with `penny db rebuild` and see exactly how your financial state is constructed.

### Multi-Account Consolidation
Import CSVs from multiple banks and accounts. Penny normalizes them into a unified view. See all your transactions and balances in one place, spanning accounts and years.

### LLM-Assisted Classification
Classification rules are Python code. Co-create them with Claude Code or other LLMs. Export unclassified transactions as Markdown, ask your LLM to suggest rules, and drop the result into Penny.

### Transfer Linking
Penny automatically links matching debit/credit pairs across accounts into transfer groups, so internal transfers don't inflate your spending reports.

**Supported banks:** Comdirect, Sparkasse (more via community contributions).

## CLI

The CLI shares state with the desktop app and is designed for LLM-assisted workflows.

```bash
# Import CSVs and apply rules
penny import ~/Downloads/umsaetze.csv
penny apply rules.py -v

# View transactions and generate reports
penny transactions list --limit 20
penny report 2024

# Inspect the vault and rebuild
penny log list
penny db rebuild
```

Full CLI documentation: [docs/CLI.md](docs/CLI.md)

## Why Penny?

Most personal finance tools require you to share bank credentials with third-party services or manually enter transactions. Penny is different:

- **No credential sharing** - You download CSVs yourself, Penny never touches your bank login
- **No cloud lock-in** - Your data lives in local files you control
- **No SaaS dependency** - The app runs entirely on your machine
- **Full audit trail** - Every number traces back to original bank records

Penny is for people who want financial clarity without giving up control of their data.

---

**Status:** Penny is in active development. Current focus is trustworthy import workflows, rule-based categorization, and transfer linking.

[Development](DEVELOPMENT.md) · [Product Vision](PRODUCT.md)
