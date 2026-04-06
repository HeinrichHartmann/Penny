# ADR-014: Predicate Language for Transaction Filtering and Classification Rules

## Status
Proposed

## Context

Penny currently exposes transaction filtering through UI controls and persists
classification behavior through Python-based rules. That is workable for the
current implementation, but it leaves a product gap:

- there is no single durable user-facing query language
- search and saved rules do not share one mental model
- persisted rule syntax is coupled to Python
- the user-visible language is not stable if the implementation language changes

This ADR is about the product surface, not just parser implementation.

The intended user is technically competent and comfortable with tables,
filters, and spreadsheets, but should not need to think in terms of writing
programs.

## Decision

Penny will use a SQL-`WHERE`-style predicate language, limited to a small
supported subset, as the user-facing language for:

- transaction list filtering
- rule creation from search or filter results
- persisted classification rules

The language is inspired by SQLite `WHERE` clauses, but Penny may enforce a
restricted grammar and a whitelist of supported fields and operators instead of
accepting arbitrary SQL.

This is a product-language decision. Parsing, evaluation, storage, and runtime
compilation are separate implementation concerns.

## Design Goals

### 1. Familiarity for the target audience

The language should feel like filtering rows in a table:

- expressing conditions over visible fields
- narrowing a transaction set
- saving a filter once it is correct

It should not feel like writing a small program.

### 2. Stability under implementation-language change

The predicate language is user-visible and durable:

- users will type it
- users may save it as rules
- it may appear in documentation, screenshots, examples, and support flows
- it may become part of exported or persisted application state

Therefore it should not be tightly coupled to Python, TypeScript, Rust, or any
other host language.

### 3. Prefer standards over invention

Predicate logic over row-like records is already a solved problem. Penny should
not invent a novel syntax unless that becomes necessary.

### 4. LLM friendliness

LLMs should be able to:

- suggest rules
- explain rules
- refactor rules
- derive rules from examples

SQL-like predicates are easier for LLMs to produce and reason about than a
bespoke DSL or host-language subset.

### 5. One language for search and rules

The same predicate language should support both:

- interactive filtering in the transaction list
- persisted categorization rules

The intended UX is:

1. search or filter until the result set is correct
2. save that predicate as a rule

## Consequences

Penny will treat this predicate language as a small, stable product interface.

Likely supported constructs include:

- `AND`, `OR`, `NOT`
- parentheses
- `=`, `!=`, `<`, `<=`, `>`, `>=`
- `IN (...)`
- possibly `LIKE`
- possibly `REGEXP` or a simpler regex operator
- a fixed set of known field names

This does not imply support for:

- `SELECT`
- joins
- subqueries
- arbitrary functions
- DDL or DML
- vendor-specific SQL features
- unrestricted execution of user SQL

The exact parsing and evaluation strategy remains intentionally separable from
the user-facing syntax.

This ADR does not require Penny to switch implementations immediately. Current
Python-based rule execution can remain as an implementation detail during a
transition, but Python should no longer be treated as the long-term user-facing
predicate language.

## Alternatives Considered

### Option A: Restricted Python expressions

Example:

```python
amount_cents < 0 and regex(payee, "amazon", "i") and account in ["Visa", "Giro"]
```

Why it was attractive:

- Python already exists in the codebase
- `ast.parse(..., mode="eval")` makes validation practical
- it is a strong short-term implementation shortcut
- it fits the current `rules.py` model

Why it was rejected as the product language:

- it couples the user-visible language to Python
- it feels like programming
- it carries host-language expectations beyond the intended problem
- it is less familiar to accountant-like and spreadsheet-oriented users

Restricted Python remains a plausible implementation technique, but not the
preferred public predicate language.

### Option B: Lucene-style or Gmail-style search syntax

Example:

```text
account:Visa amount_cents:<0 payee:/amazon/i
```

Why it was attractive:

- compact and search-oriented
- good fit for quick interactive filtering
- familiar to users of Gmail and search tools

Why it was rejected as the canonical language:

- better for ad hoc search than durable rule authoring
- often implies analyzer and tokenization semantics Penny does not want
- less aligned with explicit row predicates over finance data
- weaker fit for auditable persisted rules

This remains useful as search UX inspiration, but not as the canonical rule
language.

### Option C: SQL `WHERE`-style predicates

Example:

```sql
account = 'Visa' AND amount_cents < 0 AND payee REGEXP 'Amazon'
```

Why it was chosen:

- familiar in table and reporting contexts
- stable across backend and frontend rewrites
- aligned with SQLite without requiring full SQL
- standard rather than invented
- easy for LLMs to produce and explain
- naturally supports "search, then save as rule"

Why not full unrestricted SQL:

- too much syntax surface
- unnecessary execution and validation risk
- pushes the product toward a general query engine

### Option D: jq-style predicates

Why it was rejected:

- wrong mental model for finance users
- too tied to JSON transformation concepts
- weaker fit with row filters and spreadsheet intuition

### Option E: YAML or JSON rule DSL

Why it was attractive:

- structured and easy to validate
- good for internal representation and UI round-tripping

Why it was rejected as the primary authoring language:

- too verbose for everyday filtering
- feels like configuration, not querying
- poor fit for interactive search
- likely still requires a second user-facing query language

### Option F: Python AST as canonical rule document

Why it was attractive:

- integrates with the existing `rules.py` model
- supports advanced user-authored rules
- can be manipulated structurally

Why it was rejected for the main predicate language decision:

- solves storage representation more than user-language design
- still inherits Python coupling
- remains too code-like for the primary product surface

### Option G: JavaScript-expression subset

Why it was rejected:

- still looks like programming
- less familiar to the target audience than SQL-like filters
- carries host-language semantics that are not part of Penny's domain

### Option H: Fully custom query language

Why it was rejected:

- violates the preference for standards over invention
- increases maintenance and documentation burden
- adds little product value relative to a SQL-like subset

## Rationale Summary

The chosen direction is a SQL-`WHERE`-style subset because it best satisfies the
decisive constraints:

- familiarity for accountant-like and spreadsheet-comfortable users
- stability under implementation-language change
- alignment with SQLite and tabular finance semantics
- strong LLM ergonomics
- one language for both filtering and saved rules

## Implementation Guidance

Recommended direction:

- parse a small supported subset
- validate field names and operators strictly
- treat the language as a predicate language, not a general query language
- compile it to Penny's internal predicate representation
- optionally compile it to SQLite `WHERE` clauses where appropriate

Possible supported features:

- `AND`, `OR`, `NOT`
- parentheses
- `=`, `!=`, `<`, `<=`, `>`, `>=`
- `IN (...)`
- `LIKE`
- `REGEXP` or equivalent regex support
- fixed known fields only

Unsupported:

- arbitrary SQL
- subqueries
- joins
- statements beyond predicates
- schema access
- data mutation
- unrestricted functions

## References

- ADR-008: Transaction Classification
- ADR-013: Frontend State Architecture
