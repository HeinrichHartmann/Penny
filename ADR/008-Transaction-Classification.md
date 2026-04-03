# ADR-008: Transaction Classification

## Status
Draft

## Context

After import, Penny needs to classify transactions into user-defined categories.

The earlier design proposed:
- feature extraction at import time
- a YAML rule DSL over those features

That approach adds unnecessary complexity for the current product shape:
- it introduces a custom DSL
- it separates matching logic from the runtime language already available
- it complicates visual editing because the UI still needs an internal expression model

Penny already ships Python, and the classification boundary is trusted. So the simplest viable v1 is to treat classification rules as executable Python modules.

## Decision

### Rule Format

v1 classification rules live in a Python file, typically `rules.py`.

Example:

```python
from penny.classify import contains, regexp, rule


@rule("Income:Salary")
def salary(tx):
    return regexp(tx.memo, r"payroll") and tx.amount_cents > 0


@rule("Travel:Hotel")
def hotel(tx):
    return contains(tx.payee, "hotel")


@rule("Shopping:Amazon")
def amazon(tx):
    return contains(tx.payee, "amazon")
```

### Evaluation Model

- The rules module is loaded at runtime.
- Rules are registered in **file order** during module execution.
- Transactions are evaluated top to bottom.
- **First match wins.**
- Evaluation stops after the first matching rule.

This means source order is the precedence model.

### Runtime API

The rules module imports a tiny helper API:

```python
from penny.classify import rule, is_, contains, regexp
```

#### Decorator

```python
@rule("Shopping:Amazon")
def amazon(tx):
    return contains(tx.payee, "amazon")
```

- The category is required.
- The rule name defaults to the Python function name.
- The decorated function receives a transaction object and returns `True` or `False`.

### Helper Predicates

v1 helpers:

- `is_(value, expected)`
- `contains(value, needle)`
- `regexp(value, pattern)`

#### Semantics

- All string helpers are **case-insensitive by default**
- Matching trims leading/trailing whitespace
- `regexp()` performs regex search, not full match
- Numeric comparisons use normal Python operators directly

Example:

```python
@rule("Income:Salary")
def salary(tx):
    return regexp(tx.memo, r"payroll|gehalt") and tx.amount_cents > 0
```

### Trust Model

Rules are trusted user code.

That means:
- no sandboxing in v1
- no custom DSL parser
- no restricted execution model

This keeps the system simple and easy to evolve.

### CLI

Classification is triggered explicitly:

```bash
penny classify path/to/rules.py
```

Behavior:

1. Load `rules.py` as a Python module
2. Read all imported transactions from the database
3. Evaluate rules in file order for each transaction
4. Persist the resulting category and matching rule name
5. Print a summary

Example:

```text
$ penny classify rules.py

Loaded rules: rules.py
Rules: 3
Matched: 124
Unmatched: 18
  Income:Salary: 12
  Shopping:Amazon: 24
  Travel:Hotel: 3
```

### Persistence

Classification is stored directly on the global `transactions` table.

```sql
ALTER TABLE transactions ADD COLUMN category TEXT;
ALTER TABLE transactions ADD COLUMN classification_rule TEXT;
ALTER TABLE transactions ADD COLUMN classified_at TEXT;
```

- `category` stores the assigned category
- `classification_rule` stores the rule function name that matched
- `classified_at` stores the timestamp of the last classification pass

Re-running classification overwrites prior classification results for the current database.

### UI Model

The UI may eventually expose a structured rule editor, drag-and-drop ordering, and query-builder-like controls.

Even then, the persisted source of truth remains `rules.py`.

This keeps the runtime model stable:
- UI edits a structured internal rule list
- Penny renders that list back to Python source
- the CLI and runtime load the same generated module

### Testing Strategy

Automated tests should:
- load example `rules.py` fixtures
- verify decorator registration order
- verify helper matcher semantics
- verify full import + classify integration against sanitized CSV fixtures
- verify reclassification with a different `rules.py`

Manual tests may use local real-world exports and user-authored rules files.

## Consequences

- No YAML DSL or feature layer in v1
- The rule system is simple, expressive, and easy to debug
- File order directly controls precedence
- The future UI can still provide a visual editor while targeting Python output
- Users can edit `rules.py` directly outside the app if they want

## Out of Scope

- Rule sandboxing
- Feature extraction layer
- Multiple categories per transaction
- Partial rule evaluation plans or query compilation
- Hot reload/watch mode

## References

- ADR-007: Transaction Parsing
- Current transaction schema in `src/penny/transactions/storage.py`
