# Penny - Project Context

A desktop personal finance application for CSV-based transaction tracking and analysis.

## Quick Facts

| Attribute | Value |
|-----------|-------|
| **Language** | Python 3.11+ (backend), Vue.js 3 (frontend) |
| **Framework** | FastAPI + Uvicorn (server), Toga (native GUI) |
| **Packaging** | Briefcase (macOS .app/.dmg) |
| **Storage** | SQLite (~/.local/share/penny/) |
| **Bundle Size** | ~33 MB |
| **Dev Environment** | Nix flakes + UV |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    macOS App Bundle                      │
│  ┌─────────────┐                                        │
│  │ Toga Window │  Opens browser to localhost            │
│  └──────┬──────┘                                        │
│         │                                               │
│  ┌──────▼──────┐    ┌─────────────┐    ┌────────────┐  │
│  │   FastAPI   │◄───│   Vue.js    │    │   SQLite   │  │
│  │   Backend   │    │  Dashboard  │    │     DB     │  │
│  └──────┬──────┘    └─────────────┘    └─────┬──────┘  │
│         │                                     │         │
│  ┌──────▼─────────────────────────────────────▼──────┐  │
│  │              Python Domain Logic                   │  │
│  │  • CSV Parsing (pluggable)                        │  │
│  │  • Classification Engine                          │  │
│  │  • Account Registry                               │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
src/penny/
├── accounts/          # Account registry & reconciliation
│   ├── models.py      # Account, Subaccount dataclasses
│   ├── registry.py    # Account matching logic
│   └── storage.py     # SQLite persistence
├── api/               # FastAPI route handlers
│   ├── accounts.py    # /api/accounts endpoints
│   ├── import_.py     # /api/import endpoints
│   ├── rules.py       # /api/rules endpoints
│   └── dashboard.py   # /api/dashboard endpoints
├── ingest/            # CSV parsing plugins
│   ├── base.py        # ParserModule ABC
│   ├── detection.py   # Bank format detection
│   ├── banks/         # Custom parsers (comdirect.py, sparkasse.py)
│   └── formats/       # Shared parsing utilities
├── classify/          # Transaction classification
│   ├── engine.py      # Rule evaluation
│   └── __init__.py    # Helper predicates (is_(), contains(), regexp())
├── transactions/      # Transaction models & storage
├── static/            # Vue.js frontend
│   ├── app.js         # Main Vue application
│   ├── api.js         # API client
│   ├── charts.js      # ECharts integration
│   └── components/    # Vue components
├── launcher.py        # Toga GUI window
├── server.py          # FastAPI app setup
├── cli.py             # CLI commands
└── default_rules.py   # Starter classification rules
```

## Key Design Decisions

### CSV-Only Import (No Bank APIs)
Bank APIs are fragmented and unreliable. CSV files are stable, user-controlled, and universal across all German banks.

### Python Rules (Not YAML DSL)
Classification rules are plain Python, enabling:
- LLM co-authoring (paste transactions into Claude, get rules back)
- Full expressiveness (no custom DSL limitations)
- User trust model (rules are code, not sandboxed)

### Pluggable Parsers
Bank CSV formats are too diverse for generic parsing:
- **Custom parsers** (Comdirect) - Complex formats with special logic
- **Config-driven parsers** (Sparkasse) - JSON column mapping

### Desktop App via Briefcase
Native macOS app bundle provides:
- Standard DMG installation
- No Homebrew dependency
- Self-contained Python environment

## ADR History

| ADR | Title | Key Decision |
|-----|-------|--------------|
| **001** | Technology Choices | Briefcase + Toga for native macOS packaging |
| **002** | Product Positioning | Open-source LLM-collaborative finance tool |
| **003** | CSV Import Plugin Architecture | Pluggable parsers with common schema |
| **004** | Initial Import Design | SHA1 fingerprint deduplication, XDG storage |
| **005** | Account Register | Sequential IDs, bank+account number reconciliation |
| **006** | Frontend Bundling | Vite + npm for reproducible frontend builds |
| **007** | Transaction Parsing | Header-driven multi-section parsing |
| **008** | Transaction Classification | Python rules, file-order precedence |
| **009** | Transfer Neutralization | Union-Find grouping with user predicate |
| **011** | Layered Architecture | Interface/Domain/Model separation, no Storage classes |

## Core Data Models

### Transaction
```python
@dataclass
class Transaction:
    fingerprint: str       # SHA1 for deduplication
    account_id: int        # FK to accounts
    subaccount_type: str   # giro, visa, tagesgeld, depot
    date: date
    payee: str             # Extracted merchant name
    memo: str
    amount_cents: int      # Negative = expense
    category: str | None   # Classification result
    raw_buchungstext: str  # Original bank field
```

### Account
```python
@dataclass
class Account:
    id: int                          # Sequential (1, 2, 3...)
    bank: str                        # "comdirect", "sparkasse"
    bank_account_numbers: list[str]  # From filename
    display_name: str | None
    iban: str | None
    subaccounts: dict[str, Subaccount]
```

## Workflows

### CSV Import
1. Drop CSV file → Bank detection by filename/content
2. Parser extracts transactions, account info, balance hints
3. Account reconciliation (match existing or create new)
4. Fingerprint deduplication
5. Store in SQLite, archive raw CSV

### Classification (LLM-Collaborative)
1. Import CSVs → unclassified transactions
2. Run `penny classify rules.py`
3. Rules evaluated in file order; first match wins
4. **Iteration loop:**
   - Export unmatched as Markdown
   - Paste into Claude → get Python rules
   - Add to rules.py, re-run
   - Repeat until satisfied

## Frontend Views

| View | Purpose |
|------|---------|
| **Import** | CSV upload + file detection |
| **Accounts** | Account register + balance management |
| **Transactions** | Table with filtering, search, pagination |
| **Rules** | Rule editor + classification log |
| **Report** | ECharts dashboard (income/expense, category breakdown, Sankey) |

## Development Commands

```bash
make dev              # Toga GUI in dev mode
make serve            # Backend + Vite HMR
make test             # Run pytest
make app              # Build macOS .app + .dmg
make frontend-build   # Build bundled frontend assets
```

## Testing

10 test modules covering:
- Account registry and reconciliation
- German field extraction (Buchungstext)
- Rule evaluation and precedence
- Comdirect/Sparkasse CSV parsing
- Bank format auto-detection
- Full import pipeline integration

## Technology Rationale

| Choice | Why |
|--------|-----|
| **Python** | Data analysis ecosystem, familiar for finance |
| **FastAPI** | Lightweight, async, integrates with Python |
| **Vue.js** | Proven dashboarding experience |
| **Briefcase** | Proper macOS app structure vs PyInstaller |
| **SQLite** | Simple, self-contained, queryable, local-first |
| **Vite** | Minimal setup, fast dev, HMR support |

## Privacy Model

- All data stays local (~/.local/share/penny/)
- No cloud sync, no bank API connections
- User controls their CSV files
- Rules are local Python files
