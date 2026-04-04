# ADR-010 Implementation Plan: Portable Event-Log Storage

## Overview

Migrate from SQLite-as-source-of-truth to vault-with-replay architecture.

## Phase 1: Vault Foundation

### 1.1 Vault Directory Management

```python
# penny/vault/
#   __init__.py
#   config.py      # PENNY_VAULT_DIR, defaults
#   log.py         # LogEntry, LogManager
#   replay.py      # ReplayEngine
```

**Tasks:**
- [ ] Create `vault/` module
- [ ] Implement `VaultConfig` - resolve vault path from env/config
- [ ] Implement `LogManager` - list entries, get next sequence number, write entry
- [ ] Entry naming: `{seq:06d}_{type}.json` or `{seq:06d}_{type}/`

**Tests:**
- [ ] Test vault path resolution (env var, default)
- [ ] Test sequence number generation (empty vault, existing entries)
- [ ] Test entry ordering (lexicographic sort)

### 1.2 Event Schema

Define JSON schemas for each mutation type:

```python
# penny/vault/events.py

@dataclass
class InitEvent:
    schema_version: int = 1
    type: Literal["init"] = "init"
    timestamp: str
    app_version: str

@dataclass
class AccountCreatedEvent:
    schema_version: int = 1
    type: Literal["account_created"] = "account_created"
    timestamp: str
    bank: str
    bank_account_number: str | None
    display_name: str | None
    iban: str | None

@dataclass
class AccountUpdatedEvent:
    schema_version: int = 1
    type: Literal["account_updated"] = "account_updated"
    timestamp: str
    account_id: int
    fields: dict  # only changed fields

@dataclass
class AccountHiddenEvent:
    ...

@dataclass
class BalanceSnapshotAddedEvent:
    ...

@dataclass
class IngestManifest:
    schema_version: int = 1
    type: Literal["ingest"] = "ingest"
    timestamp: str
    csv_file_count: int
    parser: str
    parser_version: str
    app_version: str
    account_id: int  # resolved during ingest
    status: Literal["applied", "failed"]
```

**Tasks:**
- [ ] Define all event dataclasses
- [ ] Implement JSON serialization/deserialization
- [ ] Add `parser_version` property to each `BankModule`

**Tests:**
- [ ] Round-trip serialization for each event type
- [ ] Schema version is present in all events

---

## Phase 2: Replay Engine

### 2.1 Core Replay

```python
# penny/vault/replay.py

class ReplayEngine:
    def __init__(self, vault_path: Path):
        ...

    def replay(self) -> AppState:
        """Replay all log entries and return rebuilt state."""
        state = AppState()
        for entry in self.log_manager.iter_entries():
            state = self.apply(state, entry)
        return state

    def apply(self, state: AppState, entry: LogEntry) -> AppState:
        """Apply a single entry to state."""
        match entry.type:
            case "init":
                return state
            case "account_created":
                return self._apply_account_created(state, entry)
            case "ingest":
                return self._apply_ingest(state, entry)
            ...
```

**Tasks:**
- [ ] Implement `AppState` - in-memory representation of accounts, transactions, snapshots
- [ ] Implement `ReplayEngine.replay()`
- [ ] Implement handlers for each event type
- [ ] Ingest replay: read CSV from entry dir, run parser, add transactions to state

**Tests:**
- [ ] Empty vault replays to empty state
- [ ] Single account_created event produces one account
- [ ] Ingest event re-parses CSV and produces transactions
- [ ] Events applied in sequence number order
- [ ] Replay is deterministic (same vault = same state)

### 2.2 Ingest Replay

Ingest entries are directories, not single files:

```python
def _apply_ingest(self, state: AppState, entry_path: Path) -> AppState:
    manifest = self._read_manifest(entry_path / "manifest.json")

    for csv_file in entry_path.glob("*.csv"):
        content = read_file_with_encoding(csv_file)
        parser = get_parser_by_version(manifest.parser_version)
        transactions = parser.parse(csv_file.name, content, manifest.account_id)
        state.add_transactions(transactions)

    return state
```

**Tasks:**
- [ ] Implement ingest directory scanning
- [ ] Implement parser version lookup (for now: ignore version, use current)
- [ ] Handle multi-file ingests

**Tests:**
- [ ] Single CSV ingest replays correctly
- [ ] Multi-CSV ingest replays all files
- [ ] Parser is invoked with correct account_id from manifest

---

## Phase 3: Write Path

### 3.1 Mutation Recording

Every mutation now writes to the log AND updates SQLite projection.

```python
# penny/vault/mutations.py

class MutationRecorder:
    def __init__(self, log_manager: LogManager, projection: SQLiteProjection):
        ...

    def record_account_created(self, bank: str, ...) -> Account:
        # 1. Write event to log
        event = AccountCreatedEvent(...)
        entry_path = self.log_manager.write(event)

        # 2. Apply to projection (SQLite)
        account = self.projection.create_account(...)

        return account
```

**Tasks:**
- [ ] Implement `MutationRecorder` with methods for each mutation type
- [ ] Update `AccountRegistry` to use `MutationRecorder`
- [ ] Update ingest flow to create ingest directory with manifest + CSV copy
- [ ] Update balance snapshot flow
- [ ] Update rules save flow

**Tests:**
- [ ] Account creation writes event AND updates SQLite
- [ ] Ingest creates directory with manifest and CSV copy
- [ ] Event files have correct sequence numbers

### 3.2 Ingest Write Path

```python
def record_ingest(self, files: list[Path], parser: BankModule, account_id: int):
    # 1. Create ingest directory
    seq = self.log_manager.next_sequence()
    entry_dir = self.vault / "log" / f"{seq:06d}_ingest_{parser.bank}"
    entry_dir.mkdir()

    # 2. Copy CSV files (original names)
    for f in files:
        shutil.copy(f, entry_dir / f.name)

    # 3. Write manifest
    manifest = IngestManifest(
        timestamp=now_iso(),
        csv_file_count=len(files),
        parser=parser.bank,
        parser_version=f"{parser.bank}@{parser.version}",
        app_version=APP_VERSION,
        account_id=account_id,
        status="applied",
    )
    (entry_dir / "manifest.json").write_text(json.dumps(asdict(manifest)))

    # 4. Parse and add to projection
    for f in files:
        content = read_file_with_encoding(entry_dir / f.name)
        transactions = parser.parse(f.name, content, account_id)
        self.projection.store_transactions(transactions)
```

**Tasks:**
- [ ] Add `version` property to `BankModule` base class
- [ ] Implement ingest directory creation
- [ ] Copy source CSVs to vault
- [ ] Write manifest.json

**Tests:**
- [ ] Ingest creates correct directory structure
- [ ] CSV files copied with original names
- [ ] Manifest contains all required fields
- [ ] Parser version format is correct

---

## Phase 4: Startup and Projection Sync

### 4.1 Startup Flow

```python
def startup():
    vault = VaultConfig.resolve()

    if not vault.exists():
        vault.initialize()  # creates log/, writes 000001_init.json

    # Option A: Always replay (v1, simple)
    engine = ReplayEngine(vault)
    state = engine.replay()
    projection = SQLiteProjection.from_state(state)

    # Option B: Replay if projection stale (future optimization)
    # ...

    return App(vault, projection)
```

**Tasks:**
- [ ] Implement vault initialization (create dirs, write init event)
- [ ] Implement startup replay
- [ ] Wire into CLI and API entry points

**Tests:**
- [ ] Fresh start creates vault with init event
- [ ] Startup replays existing vault correctly
- [ ] Corrupted vault entry fails fast with clear error

### 4.2 Projection Rebuild

```python
# penny/vault/projection.py

class SQLiteProjection:
    @classmethod
    def from_state(cls, state: AppState, db_path: Path) -> "SQLiteProjection":
        """Rebuild SQLite from in-memory state."""
        # Drop and recreate tables
        # Insert all accounts, transactions, snapshots
        ...
```

**Tasks:**
- [ ] Implement `SQLiteProjection.from_state()`
- [ ] Ensure all current queries work against rebuilt projection

**Tests:**
- [ ] Rebuilt projection matches state exactly
- [ ] All existing queries work after rebuild

---

## Phase 5: Migration

### 5.1 Migrate Existing Data

For users with existing SQLite data but no vault:

```python
def migrate_to_vault(db_path: Path, vault_path: Path):
    """One-time migration: SQLite -> vault log."""
    vault_path.mkdir()
    (vault_path / "log").mkdir()

    log = LogManager(vault_path)

    # 1. Write init
    log.write(InitEvent(...))

    # 2. Export accounts as account_created events
    for account in read_accounts_from_sqlite(db_path):
        log.write(AccountCreatedEvent(...))

    # 3. Cannot recover original CSVs - transactions stay in SQLite only
    #    OR: prompt user to re-import from original files

    # 4. Export balance snapshots
    for snapshot in read_snapshots_from_sqlite(db_path):
        log.write(BalanceSnapshotAddedEvent(...))
```

**Decision needed:** How to handle existing transactions without source CSVs?

Options:
1. **Drop them** - user must re-import (cleanest, but disruptive)
2. **Synthetic ingest event** - create `000003_ingest_legacy/` with a `transactions.json` (breaks "raw input only" rule)
3. **Grandfather clause** - keep old SQLite data, only new ingests go to vault

**Recommendation:** Option 3 for v1. Document that vault is for new data; legacy SQLite data remains but is read-only.

**Tasks:**
- [ ] Implement migration script
- [ ] Handle "no original CSVs" case gracefully
- [ ] Add startup check: detect SQLite-only state, prompt for migration

**Tests:**
- [ ] Migration creates valid vault structure
- [ ] Accounts exported correctly
- [ ] Balance snapshots exported correctly

---

## Phase 6: Polish

### 6.1 CLI Integration

- [ ] `penny vault init` - initialize vault
- [ ] `penny vault status` - show vault path, entry count, last entry
- [ ] `penny vault replay` - force full replay and rebuild projection
- [ ] `penny vault check` - validate log integrity

### 6.2 Error Handling

- [ ] Replay failure on startup: clear error message, don't corrupt vault
- [ ] Ingest failure: don't create partial directory
- [ ] Invalid event schema: fail fast with entry path

### 6.3 Documentation

- [ ] Update README with vault concept
- [ ] Document backup procedure (just copy the vault)
- [ ] Document migration from legacy SQLite

---

## Testing Strategy

### Unit Tests
- Event serialization round-trips
- Sequence number generation
- Individual event handlers

### Integration Tests
- Full replay produces correct state
- Ingest creates correct vault structure
- Mutations write events AND update projection

### End-to-End Tests
- Fresh start → import CSV → verify vault + SQLite
- Copy vault to new location → startup → same state
- Delete SQLite → replay → data restored

### Property-Based Tests (optional)
- Arbitrary event sequences replay deterministically
- Replay(write(events)) == apply(events)

---

## Sequence

```
Phase 1 (Foundation)     [~2 days]
    ↓
Phase 2 (Replay)         [~2 days]
    ↓
Phase 3 (Write Path)     [~3 days]
    ↓
Phase 4 (Startup)        [~1 day]
    ↓
Phase 5 (Migration)      [~1 day]
    ↓
Phase 6 (Polish)         [~1 day]
```

Start with Phase 1+2 (read path), then Phase 3+4 (write path), then migration.

---

## Open Questions

1. **Vault location default** - `~/.penny/vault/` or `~/Documents/penny-vault/`?
2. **Multi-vault support** - needed for v1?
3. **Parser versioning scheme** - `comdirect@1` or semver?
4. **Rules file naming** - `000023_rules.py` or `000023_rules/rules.py`?
