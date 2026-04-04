# Penny - Claude Code Context

Personal finance app with event-sourced vault architecture.

## Quick Start

```bash
make test          # Run tests (must pass before PR)
make lint          # Check code style
make dev           # Run app in dev mode
```

## Architecture (TL;DR)

- **Vault** (`~/Documents/Penny/log/`) = source of truth (append-only event log)
- **SQLite** (`penny.db`) = derived projection, rebuildable via `penny db rebuild`
- **Backend**: FastAPI + Python 3.11+
- **Frontend**: Vue.js 3 (in `static/`)
- **Desktop**: Toga wrapper opens browser to localhost

## Key Directories

```
src/penny/
├── accounts.py      # Account model + CRUD
├── transactions.py  # Transaction model + CRUD
├── vault/           # Event-log storage
│   ├── apply.py     # Apply log entries to DB
│   ├── ingest.py    # CSV import flow
│   ├── manifests.py # Entry type definitions
│   └── replay.py    # Rebuild DB from vault
├── classify/        # Rule-based categorization
├── transfers/       # Transfer grouping (Union-Find)
├── ingest/formats/  # Bank-specific CSV parsers
└── api/             # FastAPI routes
```

## Common Tasks

| Task | Key Files |
|------|-----------|
| Add vault entry type | `vault/manifests.py`, `vault/apply.py` |
| Modify accounts | `accounts.py`, `api/accounts.py` |
| Modify transactions | `transactions.py`, `api/dashboard.py` |
| Add bank parser | `ingest/formats/`, `ingest/detection.py` |
| Change classification | `classify/engine.py` |

## Vault Entry Types

Defined in `vault/manifests.py`, applied in `vault/apply.py`:

- `init` - Vault initialization
- `ingest` - CSV import (stores original CSV)
- `account_created` - New account
- `account_updated` - Metadata change
- `account_hidden` - Archive/soft-delete (TODO: implement in apply.py)
- `balance_snapshot` - User-entered balance
- `rules` - Classification rules update

## Tests

```bash
make test                    # All tests
uv run pytest tests/test_vault.py -v  # Specific file
```

Tests use `tmp_path` fixtures - never touch real vault.

## Before Creating PR

1. Run `make test` - all tests must pass
2. Run `make lint` - no lint errors
3. Follow PR format in `agents/WORKFLOW.md`

## Key ADRs

- **ADR-010**: Vault is source of truth, SQLite is projection
- **ADR-008**: Classification uses Python rules with file-order precedence
- **ADR-011**: Flat module structure (accounts.py not accounts/model.py)

## More Details

- Full architecture: `CONTEXT.md`
- PR guidelines: `agents/WORKFLOW.md`
- Design decisions: `ADR/` directory
