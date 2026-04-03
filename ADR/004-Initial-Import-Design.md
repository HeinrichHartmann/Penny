# ADR-004: Initial Import Design

## Status
Draft

## Context

Penny needs a robust import pipeline that:
- Accepts CSV files via drag-and-drop (UI) or CLI
- Normalizes diverse bank formats into a standard schema
- Persists data in a queryable format
- Handles account detection and assignment

## Decision

### Entry Points

**1. CLI Import**
```bash
penny import <file>...
penny import ~/Downloads/*.csv
penny import --account=DE12345 ~/Downloads/unknown.csv
```

**2. UI Drag & Drop**
- Drop zone in Import view
- Same pipeline as CLI, different trigger

Both entry points feed into the same import pipeline.

### Import Pipeline

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  CSV Files  │────▶│   Detect    │────▶│  Normalize  │────▶│   Store     │
│  (input)    │     │   Account   │     │ Transactions│     │  (SQLite)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                                        │
                          ▼                                        ▼
                    ┌─────────────┐                          ┌─────────────┐
                    │ User Prompt │                          │ Raw CSV     │
                    │ (if needed) │                          │ Archive     │
                    └─────────────┘                          └─────────────┘
```

### Step 1: Account Detection

For each CSV file:

1. **Run detection plugins** - Each plugin scores confidence (0.0-1.0)
2. **Extract account info** - IBAN, bank, holder name, balance
3. **Match or create account** - Find existing account or create new

**If account cannot be determined:**
- CLI: Prompt user or require `--account=` flag
- UI: Show dialog to assign account

**Account matching:**
- Primary key: IBAN (or account_id for non-IBAN accounts)
- If IBAN matches existing account → use existing
- If new IBAN → create account record

### Step 2: Normalize Transactions

Transform bank-specific CSV into standard schema:

```python
@dataclass
class Transaction:
    fingerprint: str      # Stable ID for deduplication
    account_id: str       # FK to accounts table
    booking_date: date
    value_date: date
    amount_cents: int     # Negative = expense
    description: str      # Full text from bank
    reference: str        # Payment reference
    transaction_type: str # Bank's type (Lastschrift, etc.)
    source_type: str      # girokonto, visa, tagesgeld
    import_id: str        # FK to imports table
```

**Fingerprint calculation:**
```python
fingerprint = sha1(f"{account_id}|{booking_date}|{value_date}|{amount_cents}|{reference}")[:16]
```

**Deduplication:**
- Skip transactions with existing fingerprint
- Log skipped duplicates for user visibility

### Step 3: Store

**Directory structure (XDG Base Directory):**
```
~/.local/share/penny/          # XDG_DATA_HOME/penny
├── penny.db                   # SQLite database
└── imports/                   # Raw CSV archive
    ├── 2024-03-15_001_comdirect.csv
    ├── 2024-03-15_002_comdirect.csv
    └── ...
```

**Raw CSV Archive:**
- Copy each imported file to `imports/`
- Filename: `{date}_{seq}_{bank}.csv`
- Never modify or delete originals
- Enables re-import if schema changes

**SQLite Schema:**

```sql
-- Track each import operation
CREATE TABLE imports (
    id TEXT PRIMARY KEY,           -- UUID
    imported_at TEXT NOT NULL,     -- ISO timestamp
    source_filename TEXT NOT NULL, -- Original filename
    archive_path TEXT NOT NULL,    -- Path in imports/
    plugin_id TEXT NOT NULL,       -- Which importer was used
    account_id TEXT NOT NULL,      -- FK to accounts
    transaction_count INTEGER,
    duplicate_count INTEGER,
    warnings TEXT                  -- JSON array
);

-- Known bank accounts
CREATE TABLE accounts (
    id TEXT PRIMARY KEY,           -- IBAN or unique ID
    bank_name TEXT NOT NULL,       -- "Comdirect", "Sparkasse"
    account_type TEXT,             -- "girokonto", "visa", "tagesgeld"
    holder_name TEXT,
    display_name TEXT,             -- User-friendly name
    last_balance_cents INTEGER,
    last_balance_date TEXT,
    last_import_at TEXT,
    hidden INTEGER DEFAULT 0,      -- Tombstone flag
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Normalized transactions
CREATE TABLE transactions (
    fingerprint TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    import_id TEXT NOT NULL REFERENCES imports(id),
    booking_date TEXT NOT NULL,    -- ISO date
    value_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    description TEXT NOT NULL,
    reference TEXT,
    transaction_type TEXT,
    source_type TEXT,
    created_at TEXT NOT NULL
);

-- Indexes for common queries
CREATE INDEX idx_tx_account ON transactions(account_id);
CREATE INDEX idx_tx_booking_date ON transactions(booking_date);
CREATE INDEX idx_tx_amount ON transactions(amount_cents);
```

### CLI Interface

```bash
# Import files (auto-detect account)
penny import statement.csv

# Import with explicit account
penny import --account=DE89370400440532013000 unknown.csv

# Import multiple files
penny import ~/Downloads/*.csv

# List recent imports
penny imports list

# Show import details
penny imports show <import-id>

# Re-run import (after plugin update)
penny imports reprocess <import-id>
```

**CLI Output:**
```
$ penny import comdirect-2024-03.csv

Detecting format... Comdirect (confidence: 0.95)
Account: DE89370400440532013000 (Girokonto)

Importing transactions:
  ✓ 47 new transactions
  ○ 12 duplicates skipped
  ! 1 warning: Row 23 missing reference

Import complete: abc123
```

### Account Assignment Flow

**Auto-detected (happy path):**
```
CSV → Plugin detects bank → IBAN in header → Match/create account → Import
```

**Unknown format:**
```
CSV → No plugin matches (confidence < 0.7)
    → Error: "Unknown CSV format"
    → Show sample lines for debugging
    → User creates plugin or reports issue
```

**Known format, no IBAN:**
```
CSV → Plugin parses → No IBAN in file
    → Prompt: "Which account is this?"
    → User selects existing or enters IBAN
    → Remember association (filename pattern → account)
```

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Unknown CSV format | Error, show sample for debugging |
| Parse error on row | Warning, skip row, continue |
| Duplicate transaction | Info, skip, count in summary |
| No IBAN detected | Prompt user for account |
| File already imported | Warning, show previous import |
| Database locked | Retry with backoff, then error |

### Testing Strategy

**Unit tests:**
- Transaction fingerprint stability
- Amount parsing (German/US formats)
- Date parsing
- Account matching logic

**Integration tests:**
- Full import pipeline with sample CSVs
- Deduplication across imports
- Account creation and matching

**Test fixtures:**
- Sample CSVs from each supported bank
- Edge cases: empty files, malformed rows, encoding issues

## Consequences

- All CSV files are archived, enabling re-import
- SQLite provides queryable transaction history
- Account detection may require user input for edge cases
- Import is idempotent (duplicates skipped)
- CLI and UI share same pipeline

## Open Questions

1. Should we support importing from URLs?
2. How to handle CSV updates (same file, different content)?
3. Should archived CSVs be compressed?
