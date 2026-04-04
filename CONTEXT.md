# Penny - Project Context

A desktop personal finance application for CSV-based transaction tracking and analysis.

## Quick Facts

| Attribute | Value |
|-----------|-------|
| **Language** | Python 3.11+ (backend), Vue.js 3 (frontend) |
| **Framework** | FastAPI + Uvicorn (server), Toga (native GUI) |
| **Packaging** | Briefcase (macOS .app/.dmg) |
| **Storage** | Vault (~/Documents/Penny/) + SQLite projection |
| **Bundle Size** | ~33 MB |
| **Dev Environment** | Nix flakes + UV |
| **Tests** | 73 passing |

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    macOS App Bundle                          │
│  ┌─────────────┐                                            │
│  │ Toga Window │  Opens browser to localhost                │
│  └──────┬──────┘                                            │
│         │                                                   │
│  ┌──────▼──────┐    ┌─────────────┐    ┌────────────────┐  │
│  │   FastAPI   │◄───│   Vue.js    │    │     Vault      │  │
│  │   Backend   │    │  Dashboard  │    │ ~/Documents/   │  │
│  └──────┬──────┘    └─────────────┘    │    Penny/      │  │
│         │                               │  log/          │  │
│  ┌──────▼───────────────────────────┐  │  penny.db      │  │
│  │       Python Domain Logic         │  └───────┬────────┘  │
│  │  • CSV Parsing (pluggable)       │          │           │
│  │  • Classification Engine         │◄─────────┘           │
│  │  • Vault (event-log storage)     │   replay             │
│  └──────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
src/penny/
├── accounts.py        # Account domain: models + business logic (flattened)
├── transactions.py    # Transaction domain: models + storage (flattened)
├── config.py          # Path configuration (PENNY_DATA_DIR)
├── db.py              # Database connection management
├── sql.py             # SQL query builders
├── api/               # FastAPI route handlers
│   ├── accounts.py    # /api/accounts endpoints
│   ├── import_.py     # /api/import endpoints (uses vault)
│   ├── rules.py       # /api/rules endpoints
│   └── dashboard.py   # /api/dashboard endpoints
├── vault/             # Event-log storage (ADR-010)
│   ├── config.py      # VaultConfig (PENNY_VAULT_DIR)
│   ├── log.py         # LogManager, LogEntry
│   ├── manifests.py   # Dataclasses for entry types
│   ├── apply.py       # Apply entries to SQLite projection
│   ├── ingest.py      # CSV ingest through vault
│   └── replay.py      # ReplayEngine for state rebuild
├── ingest/            # CSV parsing plugins
│   ├── base.py        # BankModule ABC
│   ├── detection.py   # Bank format detection
│   └── formats/       # Bank-specific parsers
├── classify/          # Transaction classification
│   ├── engine.py      # Rule evaluation
│   └── __init__.py    # Helper predicates
├── static/            # Vue.js frontend
├── launcher.py        # Toga GUI window
├── server.py          # FastAPI app setup
└── cli.py             # CLI commands
```

## Vault Architecture (ADR-010)

The vault is the **source of truth**. SQLite is a derived projection that can be rebuilt via replay.

```
~/Documents/Penny/
├── log/
│   ├── 000001_init/
│   │   └── manifest.json
│   ├── 000002_ingest_comdirect/
│   │   ├── manifest.json
│   │   └── umsaetze_9788862492_20260331-1354.csv
│   └── 000003_ingest_sparkasse/
│       ├── manifest.json
│       └── 20260401-12345678-umsatz-camt52v8.CSV
└── penny.db            # Derived, rebuildable via replay
```

### Entry Types

| Type | Description | Content Files |
|------|-------------|---------------|
| `init` | Vault initialization | - |
| `ingest_{bank}` | CSV import | Original CSV file(s) |
| `account_created` | Manual account creation | - |
| `account_updated` | Account metadata change | - |
| `balance_snapshot` | User-entered balance | - |
| `rules` | Classification rules update | rules.py |

### Replay

```python
from penny.vault import replay_vault, VaultConfig

# Delete DB and rebuild from vault log
config = VaultConfig()
result = replay_vault(config)
# result.entries_processed, result.entries_by_type
```

## Key Data Flows

### CSV Import (via Vault)

```
1. User drops CSV
2. ingest_csv(request) →
   a. Detect parser from filename/content
   b. Create log entry: manifest.json + CSV copy
   c. apply_ingest(entry) →
      - Parse CSV
      - Reconcile account
      - Store transactions (with deduplication)
3. Return IngestResult
```

### Replay (Rebuild from Vault)

```
1. replay_vault(config) →
   a. init_db() - fresh schema
   b. For each log entry in sequence:
      - apply_entry(entry)
   c. Return ReplayResult
```

## ADR History

| ADR | Title | Key Decision |
|-----|-------|--------------|
| **001** | Technology Choices | Briefcase + Toga for native macOS packaging |
| **002** | Product Positioning | Open-source LLM-collaborative finance tool |
| **003** | CSV Import Plugin Architecture | Pluggable parsers with common schema |
| **004** | Initial Import Design | SHA1 fingerprint deduplication |
| **005** | Account Register | Sequential IDs, bank+account number reconciliation |
| **006** | Frontend Bundling | Vite + npm for reproducible frontend builds |
| **007** | Transaction Parsing | Header-driven multi-section parsing |
| **008** | Transaction Classification | Python rules, file-order precedence |
| **009** | Transfer Neutralization | Union-Find grouping with user predicate |
| **010** | Portable Event-Log Storage | Vault as source of truth, SQLite as projection |
| **011** | Layered Architecture | Flat modules (accounts.py, transactions.py) |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PENNY_VAULT_DIR` | `~/Documents/Penny` | Vault location (log + DB) |
| `PENNY_DATA_DIR` | `~/.local/share/penny` | Legacy data dir (used by config.py) |

**Note:** Tests set both to `tmp_path` for isolation.

## Core Data Models

### Transaction
```python
@dataclass
class Transaction:
    fingerprint: str       # SHA256[:16] for deduplication
    account_id: int        # FK to accounts
    subaccount_type: str   # giro, visa, tagesgeld, depot
    date: date
    payee: str             # Extracted merchant name
    memo: str
    amount_cents: int      # Negative = expense
    category: str | None   # Classification result
    group_id: str          # For transfer linking
```

### Account
```python
@dataclass
class Account:
    id: int
    bank: str              # "comdirect", "sparkasse"
    display_name: str | None
    iban: str | None
    holder: str | None
    subaccounts: list[Subaccount]
    created_at: datetime
    updated_at: datetime
```

## Development Commands

```bash
make dev              # Toga GUI in dev mode
make serve            # Backend + Vite HMR
make test             # Run pytest (73 tests)
make app              # Build macOS .app + .dmg
```

## Current State (Handover)

### Completed
- Vault foundation: config, log manager, manifests
- CSV import wired through vault (`ingest_csv`)
- Replay engine with deterministic state rebuild
- Flattened module structure (accounts.py, transactions.py)
- 73 tests passing

### Key Files for Vault
- `src/penny/vault/config.py` - VaultConfig class
- `src/penny/vault/log.py` - LogManager, LogEntry
- `src/penny/vault/apply.py` - apply_ingest, apply_entry
- `src/penny/vault/ingest.py` - ingest_csv, IngestRequest
- `src/penny/vault/replay.py` - ReplayEngine, replay_vault

### Tests
- `tests/test_vault.py` - Vault foundation tests (20)
- `tests/test_vault_ingest.py` - Ingest + replay tests (6)

### Next Steps (from ADR-010 Implementation Plan)
1. **Phase 4: Startup Flow** - Initialize vault on first run, replay on startup
2. **Phase 5: CLI Commands** - `penny vault init/status/replay`
3. Wire other mutations through vault (account_created, balance_snapshot, rules)

### Git
- Branch: `csv-import`
- Remote: `github` → `git@github.com:HeinrichHartmann/Penny.git`
- Status: Clean, pushed to github/csv-import
