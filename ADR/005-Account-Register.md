# ADR-005: Account Register

## Status
Draft

## Context

Bank CSV exports are frustratingly inconsistent:
- No standard header with account metadata
- IBAN rarely included (Comdirect: only account number in filename)
- Balance sometimes present, sometimes not
- One file may contain multiple subaccounts (Giro, Visa, Tagesgeld)

We need a robust Account Register that:
- Auto-creates accounts on first import with inferred metadata
- Reconciles subsequent imports to existing accounts
- Allows users to enrich account metadata via UI
- Tracks balances independently of CSV imports

## Decision

### Account Model

```
Account (1) ←──────── (*) Subaccount
   │                        │
   │                        └── giro, visa, tagesgeld, depot
   │
   └── Has metadata: IBAN, bank, holder, display_name
       Has balance (user-managed)
       Has inferred identifiers for reconciliation
```

**Account** = A bank relationship (typically one IBAN)
**Subaccount** = A product within that relationship (checking, credit card, savings)

### Schema

```python
@dataclass
class Subaccount:
    """A subaccount within a bank account."""
    type: str                    # giro, visa, tagesgeld, depot
    display_name: str | None     # User-assigned name
    last_transaction_date: date | None
    transaction_count: int

@dataclass
class Account:
    """A bank account in the register."""
    id: int                      # Internal sequence ID (1, 2, 3, ...)

    # User-editable metadata
    display_name: str | None     # "Private Checking", "Joint Account"
    iban: str | None             # DE89370400440532013000
    holder: str | None           # "Heinrich Hartmann"
    notes: str | None

    # Inferred identifiers (used for reconciliation)
    bank: str                    # "comdirect", "sparkasse"
    bank_account_numbers: list[str]  # ["9788862492"] - from filenames

    # Balance (user-managed, not from CSV)
    balance_cents: int | None
    balance_date: date | None

    # Subaccounts
    subaccounts: dict[str, Subaccount]  # type -> Subaccount

    # Metadata
    created_at: datetime
    updated_at: datetime
    hidden: bool                 # Soft delete
```

### Internal ID Strategy

Accounts use **sequential integer IDs** (1, 2, 3, ...), not IBANs:

```python
account.id = 1  # First account
account.id = 2  # Second account
```

**Rationale:**
- IBANs may be unknown initially
- Stable IDs even if IBAN is corrected later
- Simple foreign key in transactions table

**Transaction reference:**
```python
transaction.account_id = 1           # FK to account
transaction.subaccount_type = "giro" # Which subaccount
```

### Reconciliation Logic

When importing a CSV:

```python
def reconcile_account(parse_result: ParseResult, registry: AccountRegistry) -> Account:
    """Find or create account for this CSV."""

    # 1. Try exact match on bank + account number
    if account := registry.find_by_bank_account_number(
        bank=parse_result.bank,
        account_number=parse_result.bank_account_number
    ):
        return account

    # 2. Try fuzzy match on filename patterns (same bank, similar number)
    if account := registry.find_similar(parse_result):
        # Log: "Matched to existing account {account.id} by similarity"
        # Add this account number as alias
        account.bank_account_numbers.append(parse_result.bank_account_number)
        return account

    # 3. No match - create new account with inferred data
    return registry.create_account(
        bank=parse_result.bank,
        bank_account_numbers=[parse_result.bank_account_number],
        display_name=None,  # User fills in later
        # Infer what we can from CSV content
        iban=infer_iban(parse_result),
        holder=infer_holder(parse_result),
    )
```

### Inference Logic

Encapsulated in `AccountInference` class:

```python
class AccountInference:
    """Best-effort inference of account metadata from CSV."""

    def infer_iban(self, result: ParseResult) -> str | None:
        """Try to extract IBAN from CSV content."""
        # Check header lines for IBAN pattern
        # Check transaction descriptions for own IBAN
        # Return None if not found

    def infer_holder(self, result: ParseResult) -> str | None:
        """Try to extract account holder name."""
        # Check header for holder name
        # Check "Auftraggeber" in outgoing transfers
        # Return None if not found

    def infer_bank(self, filename: str, content: str) -> str:
        """Determine which bank this CSV is from."""
        # Match against known bank signatures
        # Required - must return something
```

### Balance Management

Balance is **user-managed**, not derived from CSV:

```python
# User sets initial balance
account.balance_cents = 123456  # €1,234.56
account.balance_date = date(2024, 3, 15)

# UI shows computed current balance
def current_balance(account: Account) -> int:
    """Compute current balance from base + transactions."""
    base = account.balance_cents or 0

    # Sum transactions after balance_date
    delta = sum(
        tx.amount_cents
        for tx in get_transactions(account.id)
        if tx.date > account.balance_date
    )

    return base + delta
```

**Why user-managed?**
- CSV balance is unreliable (often missing)
- User may have out-of-band knowledge
- Allows manual reconciliation
- Can set balance from bank statement

### Subaccount Detection

Subaccounts are detected from CSV section headers:

```python
SUBACCOUNT_PATTERNS = {
    "giro": ["Girokonto", "Verrechnungskonto", "Kontokorrent"],
    "visa": ["Visa-Karte", "Kreditkarte", "Visa-Umsatz"],
    "tagesgeld": ["Tagesgeld", "Sparkonto"],
    "depot": ["Depot", "Wertpapier"],
}

def detect_subaccount_type(section_header: str, transactions: list) -> str:
    """Detect subaccount type from section header or transaction types."""
    header_lower = section_header.lower()

    for subtype, patterns in SUBACCOUNT_PATTERNS.items():
        if any(p.lower() in header_lower for p in patterns):
            return subtype

    # Check transaction types as fallback
    if any("visa" in tx.transaction_type.lower() for tx in transactions):
        return "visa"

    return "giro"  # Default
```

### Import Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Drop CSV   │────▶│   Parse     │────▶│ Reconcile   │────▶│   Store     │
│             │     │             │     │  Account    │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                          ▼                    ▼
                    ParseResult          Account (existing or new)
                    - bank               - id: 1
                    - account_number     - bank: comdirect
                    - subaccounts        - subaccounts: [giro, visa]
                    - transactions
```

**On first import:**
1. Parse CSV → get bank, account_number, subaccount types
2. No match in registry → create Account(id=1)
3. Store transactions with account_id=1
4. User sees: "New account detected: Comdirect #9788862492"
5. User can add display_name, IBAN, etc.

**On subsequent import:**
1. Parse CSV → same bank, account_number
2. Match found → Account(id=1)
3. Store transactions with account_id=1
4. Deduplication skips existing transactions

### SQLite Schema

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- User-editable
    display_name TEXT,
    iban TEXT,
    holder TEXT,
    notes TEXT,

    -- Inferred/system
    bank TEXT NOT NULL,

    -- Balance (user-managed)
    balance_cents INTEGER,
    balance_date TEXT,

    -- Metadata
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    hidden INTEGER DEFAULT 0
);

-- Account numbers from various sources (filenames, etc.)
CREATE TABLE account_identifiers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    identifier_type TEXT NOT NULL,  -- "bank_account_number", "filename_pattern"
    identifier_value TEXT NOT NULL,
    UNIQUE(account_id, identifier_type, identifier_value)
);

CREATE TABLE subaccounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    type TEXT NOT NULL,             -- giro, visa, tagesgeld, depot
    display_name TEXT,
    UNIQUE(account_id, type)
);

CREATE TABLE transactions (
    fingerprint TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    subaccount_type TEXT NOT NULL,
    -- ... rest of transaction fields
);
```

### UI Considerations

**Accounts View:**
- List all accounts with display_name (or "Unknown Account #1")
- Show balance (computed), last activity
- Click to edit: display_name, IBAN, holder, notes
- Set/update balance manually

**Import feedback:**
- "Imported 47 transactions to: Private Checking (Comdirect)"
- "New account created: Comdirect #9788862492 - please add details"

## Consequences

- Accounts auto-created on first import (zero config for happy path)
- Users enrich metadata at their own pace
- Reconciliation handles messy real-world CSVs
- Balance is reliable (user-controlled, not CSV-dependent)
- Subaccounts properly modeled as part of parent account

## Open Questions

1. Should we support merging two accounts if user realizes they're the same?
2. How to handle account number changes (rare but possible)?
3. Should balance history be tracked (for reconciliation)?
