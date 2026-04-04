# ADR-011: Layered Architecture

## Status
Accepted

## Context
The codebase had grown organically with inconsistent patterns:
- `accounts/` subdirectory with `Storage` class + `Registry` class
- `transactions/` subdirectory with module-level functions
- SQL scattered across storage files
- Multiple database connection patterns (not centralized)

This made it hard to understand where logic lived and led to duplication.

## Decision
Adopt a strict three-layer architecture:

```
┌─────────────────────────────────────────────────────┐
│  Interface Layer (shallow)                          │
│  cli.py, api/*.py                                   │
│  - Parse input, call domain, format output          │
│  - NO business logic here                           │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│  Domain Layer                                       │
│  accounts.py, transactions.py, classify.py, etc.   │
│  - Business logic in pure Python                    │
│  - NO SQL here, calls sql.py for queries            │
│  - NO Storage classes, just module-level functions  │
└─────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│  Model Layer (centralized)                          │
│  sql.py  - All SQL queries, accounting math         │
│  db.py   - Connection management, schema, init      │
└─────────────────────────────────────────────────────┘
```

### Rules

1. **Interface layer is shallow**
   - CLI commands: parse args → call domain function → format output
   - API endpoints: parse request → call domain function → return JSON
   - No business logic, no SQL, no direct db access

2. **Domain layer owns business logic**
   - Module-level functions, not classes
   - `accounts.py` not `accounts/storage.py`
   - Pure Python logic (validation, transformations, orchestration)
   - Calls `sql.py` for queries, `db.connect()` for connections

3. **Model layer is centralized**
   - `sql.py`: All SQL query builders and accounting calculations
   - `db.py`: Database class, connection factory, schema definition
   - No SQL anywhere else in the codebase

4. **No Storage classes**
   - Replace `AccountStorage` class with module functions in `accounts.py`
   - Replace `TransactionStorage` with functions in `transactions.py`
   - Dataclasses for models stay in domain files or `models.py`

### File Structure (Target)

```
src/penny/
├── api/               # Interface: FastAPI endpoints (shallow)
│   ├── accounts.py
│   ├── dashboard.py
│   ├── import_.py
│   └── rules.py
├── cli.py             # Interface: CLI commands (shallow)
├── accounts.py        # Domain: account logic + Account dataclass
├── transactions.py    # Domain: transaction logic + Transaction dataclass
├── classify.py        # Domain: classification engine
├── transfers.py       # Domain: transfer linking
├── ingest/            # Domain: CSV parsing (complex enough for submodule)
├── sql.py             # Model: all SQL queries
├── db.py              # Model: connection management, schema
├── config.py          # Shared config (paths, env vars)
└── static/            # Frontend assets
```

## Consequences

### Positive
- Clear separation of concerns
- Easy to find where logic lives
- SQL centralized for review and optimization
- No class ceremony for simple CRUD
- Easier testing (mock sql.py or db.py)

### Negative
- Refactoring required to flatten existing structure
- Module-level functions lose some encapsulation
- Large sql.py file (mitigate with clear sections)

### Migration Path
1. Move SQL from storage files to `sql.py`
2. Convert Storage classes to module functions
3. Flatten subdirectories (`accounts/` → `accounts.py`)
4. Verify interface layer is shallow (no business logic in cli.py/api/)
