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
- [ ] Implement `VaultConfig` - resolve vault path (default: `~/Documents/Penny`)
- [ ] Implement `LogManager` - list entries, get next sequence number, write entry
- [ ] Entry naming: `{seq:06d}_{type}/` (all entries are directories)

**Tests:**
- [ ] Test vault path resolution (env var, default)
- [ ] Test sequence number generation (empty vault, existing entries)
- [ ] Test entry ordering (lexicographic sort)

### 1.2 Entry Structure

All log entries are directories with `manifest.json` + optional content files:

```text
000001_init/
  manifest.json

000002_account_created/
  manifest.json

000003_ingest_comdirect/
  manifest.json
  umsaetze_9788862492_20260331-1354.csv

000004_balance_snapshot/
  manifest.json

000005_rules/
  manifest.json
  rules.py
```

### 1.3 Manifest Schema

```python
# penny/vault/manifests.py

@dataclass
class InitManifest:
    schema_version: int = 1
    type: Literal["init"] = "init"
    timestamp: str
    app_version: str

@dataclass
class AccountCreatedManifest:
    schema_version: int = 1
    type: Literal["account_created"] = "account_created"
    timestamp: str
    bank: str
    bank_account_number: str | None
    display_name: str | None
    iban: str | None

@dataclass
class AccountUpdatedManifest:
    schema_version: int = 1
    type: Literal["account_updated"] = "account_updated"
    timestamp: str
    account_id: int
    fields: dict  # only changed fields

@dataclass
class BalanceSnapshotManifest:
    schema_version: int = 1
    type: Literal["balance_snapshot"] = "balance_snapshot"
    timestamp: str
    account_id: int
    subaccount_type: str
    snapshot_date: str
    balance_cents: int

@dataclass
class IngestManifest:
    schema_version: int = 1
    type: Literal["ingest"] = "ingest"
    timestamp: str
    csv_files: list[str]  # original filenames
    parser: str
    parser_version: str
    app_version: str
    status: Literal["applied", "failed"]

@dataclass
class RulesManifest:
    schema_version: int = 1
    type: Literal["rules"] = "rules"
    timestamp: str
    app_version: str
```

**Tasks:**
- [ ] Define all manifest dataclasses
- [ ] Implement JSON serialization/deserialization
- [ ] Add `version` property to each `BankModule`

**Tests:**
- [ ] Round-trip serialization for each manifest type
- [ ] Schema version is present in all manifests

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

## Phase 5: Polish

### 5.1 CLI Integration

- [ ] `penny vault init` - initialize vault
- [ ] `penny vault status` - show vault path, entry count, last entry
- [ ] `penny vault replay` - force full replay and rebuild projection
- [ ] `penny vault check` - validate log integrity

### 5.2 Error Handling

- [ ] Replay failure on startup: clear error message, don't corrupt vault
- [ ] Ingest failure: don't create partial directory
- [ ] Invalid manifest schema: fail fast with entry path

### 5.3 Documentation

- [ ] Update README with vault concept
- [ ] Document backup procedure (just copy the vault)

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
Phase 1 (Foundation)
    ↓
Phase 2 (Replay)
    ↓
Phase 3 (Write Path)
    ↓
Phase 4 (Startup)
    ↓
Phase 5 (Polish)
```

Start with Phase 1+2 (read path), then Phase 3+4 (write path), then polish.

---

## Decisions

1. **Vault location default** - `~/Documents/Penny` (human-readable, easy to backup/archive)
2. **Migration** - Not supported. Pre-alpha users must re-import. No legacy SQLite support.
3. **Log entry format** - All entries are directories with `manifest.json` + content files. No bare JSON files.
