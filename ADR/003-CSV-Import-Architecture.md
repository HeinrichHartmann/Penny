# ADR-003: CSV Import Plugin Architecture

## Status
Draft

## Context

Penny needs to import bank transaction data from CSV files. Each bank has unique formats requiring dedicated parsers.

## Reference Implementation

We adopt the architecture from [You Need A Parser (YNAP)](https://github.com/leolabs/you-need-a-parser), a TypeScript project supporting 110+ bank formats. Our Python implementation mirrors this design.

**Key insight from YNAP:** Two parser types coexist:
1. **Custom parsers** - For complex formats (e.g., Comdirect with structured Buchungstext)
2. **Config-driven parsers** - For simple column-mapping formats (e.g., Sparkasse variants)

## Decision

### Output Schema

Adapted from YNAP's `YnabRow`, extended for our needs:

```python
@dataclass
class Transaction:
    """Normalized transaction - output of all parsers."""
    date: date              # Booking date (Buchungstag)
    payee: str              # Extracted counterparty name
    memo: str               # Transaction description/reference
    amount_cents: int       # Negative = outflow, positive = inflow

    # Extended fields (not in YNAP)
    account_id: str         # IBAN:subaccount (e.g., "DE123:giro", "DE123:visa")
    value_date: date | None # Wertstellung if available
    transaction_type: str   # Bank's type (Lastschrift, Kartenverfügung, etc.)
    raw_data: dict          # Original row for debugging
```

### Parser Interface

Direct port from YNAP's `ParserModule`:

```python
from abc import ABC, abstractmethod
from pathlib import Path

class ParserModule(ABC):
    """Base class for CSV parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name, e.g. 'Comdirect'."""
        pass

    @property
    @abstractmethod
    def country(self) -> str:
        """ISO country code, e.g. 'de'."""
        pass

    @property
    @abstractmethod
    def filename_pattern(self) -> re.Pattern:
        """Regex for matching filenames."""
        pass

    @abstractmethod
    def match(self, filename: str, content: str) -> bool:
        """
        Return True if this parser can handle the file.
        Called with file content for inspection.
        """
        pass

    @abstractmethod
    def parse(self, filename: str, content: str) -> ParseResult:
        """
        Parse file content and return normalized transactions.
        """
        pass
```

### Account Identification

**See [ADR-005: Account Register](./005-Account-Register.md) for full account model.**

**Summary:**
- Accounts use sequential integer IDs (1, 2, 3)
- Accounts have subaccounts: giro, visa, tagesgeld, depot
- Parser extracts `bank_account_number` from filename
- Reconciliation matches to existing account or creates new one
- Metadata (IBAN, holder, display_name) inferred or user-provided

**Subaccount types** (detected from CSV section headers):
- `giro` - "Umsätze Girokonto" / "Umsätze Verrechnungskonto"
- `visa` - "Umsätze Visa-Karte" (or "Visa-Umsatz" transaction type)
- `tagesgeld` - "Umsätze Tagesgeld PLUS-Konto"
- `depot` - "Umsätze Depot"

### Balance Extraction

Comdirect CSV may include balance in footer (inconsistently present):

```
...transactions...
"Alter Kontostand";"1.234,56 EUR";
"Neuer Kontostand";"2.345,67 EUR";
```

**Extraction strategy:**
1. After parsing transactions, scan remaining lines for each section
2. Look for `"Alter Kontostand"` or `"Neuer Kontostand"`
3. Parse German number format → cents
4. Store as hint, but balance is ultimately user-managed (see ADR-005)

**Note:** In practice, many Comdirect exports lack balance lines. Balance is user-managed in the Account Register.

### Parse Result

```python
@dataclass
class ParsedSection:
    """A section within a multi-section CSV (e.g., Giro, Visa, Depot)."""
    subaccount_type: str          # giro, visa, tagesgeld, depot
    section_header: str           # Original header (e.g., "Umsätze Girokonto")
    balance_cents: int | None     # From "Neuer Kontostand" if present
    transaction_count: int

@dataclass
class ParseResult:
    """Result of parsing a CSV file."""
    bank: str                     # e.g., "comdirect"
    filename: str                 # Original filename
    bank_account_number: str      # From filename (e.g., "9788862492")
    sections: list[ParsedSection] # One per section in multi-section files
    transactions: list[Transaction]
    warnings: list[str]
```

**Pipeline after parsing:**
```python
# 1. Parse CSV
result = parser.parse(filename, content)

# 2. Reconcile to account (find existing or create new)
account = registry.reconcile(result)  # Returns Account with id=1, 2, etc.

# 3. Assign account_id to transactions
for tx in result.transactions:
    tx.account_id = account.id  # Integer FK

# 4. Store transactions (with deduplication)
storage.store_transactions(result.transactions)
```

### Parser Types

#### 1. Custom Parsers

For banks with complex formats requiring special logic.

**Example: Comdirect** (reference: `ynap-parsers/src/de/comdirect/comdirect.ts`)

```python
class ComdirectParser(ParserModule):
    """
    Comdirect CSV parser.

    Format characteristics:
    - Multi-section: One file contains Girokonto, Visa, Tagesgeld sections
    - Section header: "Umsätze Girokonto" / "Umsätze Visa-Karte" etc.
    - Columns vary by section type:
      - Giro/Tagesgeld: Buchungstag, Wertstellung (Valuta), Vorgang, Buchungstext, Umsatz in EUR
      - Visa: Buchungstag, Umsatztag, Vorgang, Referenz, Buchungstext, Umsatz in EUR
    - Footer: "Alter Kontostand" / "Neuer Kontostand" (per section)
    - Buchungstext contains structured fields:
      - Empfänger: / Auftraggeber: / Zahlungspflichtiger:
      - Kto/IBAN:, BLZ/BIC:, Ref:, Buchungstext:
    - Encoding: CP1252 (Windows)
    """

    name = "Comdirect"
    country = "de"
    filename_pattern = re.compile(r'^umsaetze_\d+_[\d-]+\.csv$')

    def match(self, filename: str, content: str) -> bool:
        # Primary: section header signature
        if '"Umsätze Girokonto"' in content or '"Umsätze Verrechnungskonto"' in content:
            return True

        # Secondary: required columns present
        required = ['Buchungstag', 'Buchungstext', 'Umsatz in EUR']
        return all(col in content for col in required)

    def parse(self, filename: str, content: str) -> ParseResult:
        # 1. Split into sections by "Umsätze X" headers
        # 2. For each section:
        #    a. Detect subaccount type (giro, visa, tagesgeld)
        #    b. Extract IBAN from header metadata if present
        #    c. Parse transactions with section-specific schema
        #    d. Extract balance from footer ("Neuer Kontostand")
        # 3. Extract payee from Buchungstext using field markers
        # 4. Build account_id as "IBAN:subaccount"
        ...
```

**Buchungstext field extraction** (from YNAP):
```python
FIELD_MARKERS = ['Buchungstext', 'Empfänger', 'Auftraggeber',
                 'Zahlungspflichtiger', 'Kto/IBAN', 'BLZ/BIC', 'Ref']

def extract_field(posting_text: str, field: str) -> str | None:
    """Extract a field value from structured Buchungstext."""
    # Split by field name, then by next field marker
    # Example: "Empfänger: REWE Kto/IBAN: DE123" -> "REWE"
```

#### 2. Config-Driven Parsers

For banks with simple column layouts, use JSON configuration.

**Example: Sparkasse** (reference: `ynap-parsers/src/bank2ynab/banks.json`)

```json
{
  "name": "Sparkasse Rhein-Neckar-Nord",
  "country": "de",
  "filename_pattern": "[0-9]{8}-[0-9]{8}-umsatz\\.csv",
  "date_format": "%d.%m.%y",
  "header_rows": 1,
  "footer_rows": 0,
  "columns": {
    "date": 1,
    "memo": 3,
    "payee": 11,
    "amount": 14
  }
}
```

**Config parser generator:**
```python
def make_config_parser(config: dict) -> ParserModule:
    """Generate a parser from JSON configuration."""

    class ConfigParser(ParserModule):
        name = config["name"]
        country = config["country"]
        filename_pattern = re.compile(config["filename_pattern"])

        def match(self, filename: str, content: str) -> bool:
            if not self.filename_pattern.match(filename):
                return False
            # Validate date column contains valid dates
            # Validate amount column contains numbers
            ...

        def parse(self, filename: str, content: str) -> ParseResult:
            # Skip header_rows, footer_rows
            # Map columns by index
            # Parse dates with date_format
            ...

    return ConfigParser()
```

### File Detection Flow

Mirror YNAP's `matchFile` logic:

```python
def match_file(filename: str, content: str) -> list[ParserModule]:
    """Find parsers that can handle this file."""

    # 1. Try filename pattern matches first
    filename_matches = [p for p in parsers if p.filename_pattern.match(filename)]
    if filename_matches:
        matches = [p for p in filename_matches if p.match(filename, content)]
        if matches:
            return matches

    # 2. Fall back to content-based matching
    return [p for p in parsers if p.match(filename, content)]
```

### Encoding Handling

German bank CSVs often use Windows-1252 (CP1252) encoding:

```python
def read_file(path: Path) -> str:
    """Read file with encoding detection."""
    content = path.read_bytes()

    # Try UTF-8 first
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # Fall back to CP1252 (common for German banks)
    return content.decode('cp1252')
```

### Number Parsing

German format uses comma as decimal separator:

```python
def parse_german_amount(s: str) -> int:
    """Parse German number format to cents.

    '1.234,56' -> 123456
    '-1.234,56' -> -123456
    """
    s = s.strip().replace('.', '').replace(',', '.')
    return int(float(s) * 100)
```

### Initial Parsers

**v0.1 ships with:**

| Parser | Type | Source |
|--------|------|--------|
| Comdirect | Custom | Port from `de/comdirect/comdirect.ts` |
| Sparkasse (generic) | Config | Port from `bank2ynab/banks.json` |

**Sparkasse variants** (from YNAP banks.json):
- Sparkasse Rhein-Neckar-Nord
- Sparkasse Südholstein
- Ostseesparkasse Rostock (checking + credit card)

All share similar structure, differ in column positions.

### Directory Structure

```
penny_import/
├── __init__.py
├── base.py              # ParserModule, Transaction, ParseResult
├── registry.py          # Parser registration and matching
├── encoding.py          # File encoding detection
├── parsers/
│   ├── __init__.py
│   ├── comdirect.py     # Custom parser
│   └── config_parser.py # Config-driven parser generator
├── configs/
│   └── banks.json       # Sparkasse and other simple formats
└── utils.py             # German number parsing, date parsing
```

## Consequences

- Architecture proven by YNAP's 110+ bank support
- Custom parsers for complex formats (Comdirect)
- Config-driven parsers for simple formats (Sparkasse)
- Easy to add new banks: either config JSON or custom parser
- Python port maintains same logic, easier to extend

## References

- YNAP source: `src/you-need-a-parser/` (cloned locally)
- Comdirect parser: `packages/ynap-parsers/src/de/comdirect/comdirect.ts`
- Bank configs: `packages/ynap-parsers/src/bank2ynab/banks.json`
- Parser interface: `packages/ynap-parsers/src/index.ts`
