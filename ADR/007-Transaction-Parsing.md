# ADR-007: Transaction Parsing

## Status
Draft

## Context

With account detection and registry in place (ADR-003, ADR-005), Penny needs to parse actual transaction data from CSV files. This ADR defines the v0.2 transaction extraction pipeline.

**Reference Implementation:** [You Need A Parser (YNAP)](https://github.com/leolabs/you-need-a-parser) - TypeScript project supporting 110+ bank formats. We port the Comdirect parser logic directly where it fits the Penny account model.

**Local source:** `src/you-need-a-parser/packages/ynap-parsers/src/de/comdirect/comdirect.ts`

## Decision

### Parser Selection Strategy

**Default mode:** Penny infers the parser from filename + content.

```
CSV File
    |
    |- Filename: umsaetze_9788862492_20260331-1354.csv
    |             -> Comdirect pattern
    |
    \- Content: "Umsätze Girokonto"
                  -> Comdirect signature

    => Parser: comdirect
```

**Explicit override:** The CLI also supports `--csv-type` to force a parser.

```bash
penny import --csv-type comdirect umsaetze_9788862492_20260331-1354.csv
```

**v1 scope:** `--csv-type` is the first explicit override. The CLI help should document the supported parser names.

**Future fallback:** If parser inference works but account inference does not, we may add `--account/-a` so the user can import into a specific account manually.

```bash
# Future/manual fallback
penny import --csv-type comdirect --account 1 ambiguous-export.csv
```

### Global Transaction Schema

All bank parsers normalize into a **single global `transactions` table**. There is no per-bank transaction table.

```python
@dataclass
class Transaction:
    """Parsed transaction ready for storage."""
    fingerprint: str          # Unique ID for deduplication
    account_id: int           # FK to accounts table
    subaccount_type: str      # giro, visa, tagesgeld, depot

    # Core fields
    date: date                # Buchungstag (booking date)
    payee: str                # Extracted counterparty
    memo: str                 # Transaction description
    amount_cents: int         # Negative = outflow, positive = inflow

    # Extended fields
    value_date: date | None   # Wertstellung / Umsatztag / value date
    transaction_type: str     # Vorgang (Lastschrift, Kartenverfügung, etc.)
    reference: str | None     # Ref. number from Buchungstext or CSV column

    # Raw data for debugging
    raw_buchungstext: str     # Original Buchungstext field
    raw_row: dict             # Original CSV row
```

**Normalization rule:** Parsing is bank-specific, storage is not. The parser is responsible for mapping section-specific columns into this shared schema.

### Comdirect Parsing Logic

#### Section-Aware, Header-Driven Parsing

Comdirect exports are **multi-section** and **section schemas differ**. The parser must therefore be:

1. **Section-aware** - split one file into Giro, Visa, Tagesgeld, Depot sections
2. **Header-driven** - map fields by section header names, not fixed column positions

This is required because Comdirect section layouts differ.

**Example Giro section**
```csv
"Umsätze Girokonto";"Zeitraum: 01.01.2024 - 01.03.2026";
"Buchungstag";"Wertstellung (Valuta)";"Vorgang";"Buchungstext";"Umsatz in EUR";
"27.02.2026";"27.02.2026";"Lastschrift / Belastung";"Auftraggeber: AMAZON...";"-37,99";
```

**Example Visa section**
```csv
"Umsätze Visa-Karte";"Zeitraum: 01.01.2024 - 01.03.2026";
"Buchungstag";"Umsatztag";"Vorgang";"Referenz";"Buchungstext";"Umsatz in EUR";
"27.02.2026";"26.02.2026";"Visa-Umsatz";"123456";"HOTEL EXAMPLE";"-37,99";
```

**Implication:** The parser must locate the header row inside each section, build a header map, and then read fields by semantic column name.

#### Column Mapping per Section Type

| Transaction Field | Giro/Tagesgeld | Visa |
|-------------------|----------------|------|
| `date` | Buchungstag | Buchungstag |
| `value_date` | Wertstellung (Valuta) | Umsatztag |
| `transaction_type` | Vorgang | Vorgang |
| `memo` | Buchungstext → extract | Buchungstext |
| `payee` | Buchungstext → extract | Buchungstext (or merchant name) |
| `reference` | Buchungstext → extract `Ref.` | Referenz column |
| `amount_cents` | Umsatz in EUR | Umsatz in EUR |

**Notes:**
- Giro `Buchungstext` is structured (contains `Auftraggeber:`, `Buchungstext:`, `Ref.` markers) → requires field extraction
- Visa `Buchungstext` is typically plain merchant text → use directly as memo/payee
- Visa has explicit `Referenz` column → use directly, no extraction needed

```python
def parse_comdirect(filename: str, content: str, account_id: int) -> list[Transaction]:
    transactions = []

    for section_header, section_content in split_sections(content):
        subaccount = detect_subaccount(section_header)
        rows = read_section_rows(section_content)
        header_map = build_header_map(rows)

        for row in iter_transaction_rows(rows, header_map):
            tx = parse_row(row, header_map, account_id, subaccount)
            if tx is not None:
                transactions.append(tx)

    return transactions
```

**Not acceptable:** A parser that assumes the same fixed positional columns for every Comdirect section.

#### Buchungstext Field Extraction

The `Buchungstext` field contains structured data with markers:

```
Auftraggeber: AMAZON PAYMENTS EUROPE S.C.A. Buchungstext: 028-7214985-6053918 AMZN Mktp DE Ref. 9L2C28W229K9DKRY/41682
```

**Field markers (from YNAP):**
```python
POSTING_TEXT_FIELDS = [
    'Buchungstext',
    'Empfänger',
    'Auftraggeber',
    'Zahlungspflichtiger',
    'Kto/IBAN',
    'BLZ/BIC',
    'Ref',
]
```

**Payee priority (from YNAP):**
```python
payee = (
    extract_field(buchungstext, 'Empfänger') or
    extract_field(buchungstext, 'Zahlungspflichtiger') or
    extract_field(buchungstext, 'Auftraggeber')
)
```

**Field extraction:**
```python
def extract_field(posting_text: str, field: str) -> str | None:
    """Extract a field value from structured Buchungstext."""
    parts = posting_text.split(field)
    if len(parts) < 2:
        return None

    pattern = '|'.join(re.escape(f) for f in POSTING_TEXT_FIELDS)
    raw_content = re.split(f'({pattern})', parts[1], maxsplit=1)[0]

    return re.sub(r'^[:.\s]+|\s+$', '', raw_content) or None
```

**Reference precedence:** Use the dedicated CSV `Referenz` column when present; otherwise extract `Ref.` from `Buchungstext`.

#### Row Filtering

```python
# Skip pending transactions and rows without amount
if row['Buchungstag'] == 'offen' or not amount_value:
    continue
```

Skip non-transaction rows such as footers, balances, and blank lines.

#### Subaccount Detection

```python
def detect_subaccount(section_header: str) -> str:
    """Detect subaccount type from section header."""
    header_lower = section_header.lower()
    if "visa" in header_lower:
        return "visa"
    if "tagesgeld" in header_lower:
        return "tagesgeld"
    if "depot" in header_lower:
        return "depot"
    return "giro"
```

### Fingerprint Generation

Transactions need stable IDs for deduplication across imports:

```python
import hashlib

def generate_fingerprint(
    account_id: int,
    date: date,
    amount_cents: int,
    payee: str,
    reference: str | None,
) -> str:
    if reference:
        key = f"{account_id}:{reference}"
    else:
        key = f"{account_id}:{date.isoformat()}:{amount_cents}:{payee[:50]}"

    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

**Note:** Comdirect `Ref.` numbers appear unique per transaction, making fingerprinting reliable when present.

### SQLite Schema

```sql
CREATE TABLE transactions (
    fingerprint TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    subaccount_type TEXT NOT NULL,

    -- Core fields
    date TEXT NOT NULL,
    payee TEXT NOT NULL,
    memo TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,

    -- Extended fields
    value_date TEXT,
    transaction_type TEXT,
    reference TEXT,

    -- Raw data (JSON)
    raw_buchungstext TEXT,
    raw_row TEXT,

    -- Metadata
    imported_at TEXT NOT NULL,
    source_file TEXT
);

CREATE INDEX idx_transactions_account ON transactions(account_id);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_payee ON transactions(payee);
```

### Import Flow

```
penny import umsaetze_9788862492_20260331-1354.csv

1. Read file (UTF-8 with CP1252 fallback)
2. Select parser
   - auto-detect by default
   - or explicit via --csv-type
3. Detect account metadata from file
4. Reconcile to registry
5. Parse transactions section-by-section
6. Store in global transactions table with deduplication
7. Report new vs duplicate counts
```

### CLI Output

```text
$ penny import --csv-type comdirect ~/Downloads/umsaetze_9788862492_20260331-1354.csv

Detected: Comdirect
Account: #1 (comdirect 9788862492)
Sections: giro, visa

Importing...
  New: 47 transactions
  Duplicates: 95 (skipped)

Done.
```

### Testing Strategy

**Automated tests (`pytest`):**
- Use committed, sanitized CSV fixtures in the repo
- Cover section splitting, header detection, date/amount parsing, Buchungstext extraction, and deduplication
- Cover multi-section files (for example giro + visa in one file)

**Manual tests:**
- Run against local real-world CSV exports in `./data` or other developer-local folders
- Use these for parser refinement, but not as required test inputs for CI or `pytest`

### Utility Functions

```python
def parse_german_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%d.%m.%Y").date()

def parse_german_amount(s: str) -> int:
    s = s.strip().replace('.', '').replace(',', '.')
    return int(round(float(s) * 100))

def read_file_with_encoding(path: Path) -> str:
    content = path.read_bytes()
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        return content.decode('cp1252')
```

## Consequences

- Comdirect parsing is robust to section-specific column layouts
- All imported transactions share one normalized schema and one transaction table
- `--csv-type` provides an explicit parser override without committing yet to manual account selection
- Fixture-based automated tests are reproducible across machines
- Raw source rows remain available for debugging parser issues

## Out of Scope

- Transaction categorization
- Balance reconciliation
- Config-driven parsers for other banks
- Split transactions
- Manual account override via `--account/-a` in v0.2

## References

- YNAP: https://github.com/leolabs/you-need-a-parser
- Local parser reference: `src/you-need-a-parser/`
- ADR-003: CSV Import Plugin Architecture
- ADR-005: Account Register
