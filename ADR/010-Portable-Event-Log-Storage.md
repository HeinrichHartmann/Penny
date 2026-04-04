# ADR-010: Portable Financial State Storage

## Status
Draft

## Context

Penny needs a storage model that is:

- portable between machines
- easy to back up
- explicit and user-owned
- inspectable outside the app
- stable enough to rebuild financial state after local breakage

The previous direction of storing every mutation as a filesystem event-log entry was too heavy for the actual product needs.

The important user-owned artifacts are:

- raw import files
- financial/user-decision mutations
- rules history

The user does not need to inspect or edit every internal application mutation as a directory tree.

## Decision

### User-Owned Penny Directory

Penny stores its portable state under a user-owned directory.

Default location: `~/Documents/Penny`

Example:

```text
~/Documents/Penny/
  penny.sqlite
  mutations.tsv
  imports/
    000001-2026-04-04T11:19:00Z/
      manifest.json
      umsaetze_9788862492_20260331-1354.csv
    000002-2026-04-05T09:10:00Z/
      manifest.json
      20260401-12345678-umsatz-camt52v8.CSV
  rules/
    2026-04-04T11:22:00Z_rules.py
    2026-04-05T09:10:00Z_rules.py
```

This directory is the unit of backup and migration.

### Current-State SQLite Database

`penny.sqlite` is the current materialized application state only.

It is not the archival format and not the primary portability boundary.

It should be largely rebuildable from:

- `imports/`
- `mutations.tsv`
- `rules/`

The rebuildability contract is about the financial numbers and user financial decisions, not every incidental application setting.

### Rebuildability Contract

Penny must be able to rebuild the financial state that affects reports and balances, including:

- imported transactions
- account identities relevant to reconciliation
- account naming and metadata that affect interpretation/display
- account balance snapshots
- manual transaction groupings
- manual classification actions
- active and historical rule sets

Penny does not need to guarantee replay of purely incidental UI/application state, such as:

- active filters
- selected tabs
- window layout
- temporary caches
- other cosmetic or convenience preferences

In short:

- the numbers must be rebuildable
- the app chrome does not have to be

### Raw Imports as Directories

Accepted CSV drops are archived under `imports/` as append-only directories.

Each ingest gets:

- a monotonic numeric prefix
- an ingest timestamp in the folder name
- a `manifest.json`
- the original uploaded CSV file(s)

Example:

```text
imports/
  000001-2026-04-04T11:19:00Z/
    manifest.json
    umsaetze_9788862492_20260331-1354.csv
```

The manifest records metadata such as:

- ingest timestamp
- parser
- parser version
- application version
- ingest status
- CSV file list
- file hashes

If a dropped file cannot be parsed, Penny rejects it and does not create an import directory.

### Mutation Log as TSV

Non-import financial/user-decision mutations are stored in a single append-only TSV file:

```text
~/Documents/Penny/mutations.tsv
```

The format is chosen because it is:

- inspectable
- diffable
- append-only
- easy to open in spreadsheet software

The TSV has a fixed envelope with a JSON payload column.

Suggested columns:

```text
seq	timestamp	type	entity_type	entity_id	payload_json
```

The first columns remain easy to inspect in spreadsheet tools; the payload stays flexible enough for future schema evolution.

Examples of mutations captured there:

1. account balance setting
2. account naming / account metadata updates
3. manual transaction groupings
4. manual classification actions

Additional financial mutations may be added later using new `type` values.

### Rules History as Versioned Python Files

Rules are persisted as versioned Python files under `rules/`.

Example:

```text
rules/
  2026-04-04T11:22:00Z_rules.py
  2026-04-05T09:10:00Z_rules.py
```

This preserves:

- exact classifier code history
- easy manual inspection
- compatibility with the existing Python rules model

Rules updates should also append a corresponding row to `mutations.tsv`, so the mutation log references which rule snapshot became active.

### Replay Model

When Penny needs to rebuild financial state, it should do so from:

1. `imports/`
2. `mutations.tsv`
3. `rules/`

`penny.sqlite` may be recreated from those sources.

The replay model is therefore selective:

- import artifacts and financial mutations are durable source material
- SQLite is a working projection

This keeps the portability boundary small and explicit without forcing every internal mutation into a bespoke directory log.

### UI Implication

The current import surface should evolve into an import history view.

That view should show:

- every accepted import
- import date
- number of CSV files
- parser used
- parser version used at the time
- status/failures recorded in the import manifest

This makes the import tab meaningful as an auditable history of raw financial inputs.

### Compatibility Contract

The compatibility boundary is:

- import directory format
- `mutations.tsv` row format
- rules snapshot layout

Penny should remain backwards-compatible at that storage boundary.

That means:

- older import manifests must remain readable
- older mutation rows must remain replayable
- new mutation kinds should be additive
- old records must not be silently reinterpreted incompatibly

## Consequences

- Penny remains portable by copying one user-owned directory
- raw CSV provenance stays explicit and inspectable
- the mutation log is easier to inspect than JSON-per-directory entries
- rules history remains human-readable Python
- SQLite becomes a disposable current-state projection
- the product avoids over-engineering a filesystem WAL for mutations the user never interacts with directly

## Out of Scope

- exact TSV schema details for every mutation kind
- compression/retention policies for old imports
- cross-machine sync protocol
- non-financial UI preference persistence

## References

- ADR-007: Transaction Parsing
- ADR-008: Transaction Classification
- ADR-009: Account Balance Snapshots
