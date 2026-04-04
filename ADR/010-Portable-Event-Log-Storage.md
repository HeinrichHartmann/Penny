# ADR-010: Portable Event-Log Storage

## Status
Draft

## Context

Penny currently persists application state in local app storage under XDG-style directories and SQLite tables.

That is convenient for implementation, but it is a poor fit for the product requirements:

- users should be able to move Penny to a new machine without uncertainty
- backups should be simple and explicit
- the full state should be inspectable and user-owned
- rebuilding state should not depend on hidden internal app directories
- parser or classifier changes must not silently rewrite past imports

For a finance tool, "the database in app state" is too opaque. Penny needs a portable source of truth.

## Decision

### User-Owned Vault Directory

Penny's source of truth is a user-owned vault directory.

Example:

```text
penny-vault/
  log/
    000001_init.json
    000002_account_created.json
    000003_import_comdirect/
      event.json
      source.csv
      transactions.jsonl
    000004_account_updated.json
    000005_balance_snapshot_added.json
    000023_rules.py
```

The vault is:

- portable
- backupable
- inspectable
- intended to be copied between machines

### Append-Only Mutation Log

Every user-visible mutation becomes a new log entry.

Examples:

- account created
- account metadata updated
- account hidden
- balance snapshot added
- balance snapshot edited
- transaction override added
- transfer group edited
- CSV imported
- rules updated

The log is append-only:

- existing entries are immutable
- ordering is defined by the numeric prefix
- replaying entries in order reconstructs the full state

### Replay Model

Penny rebuilds application state by replaying the mutation log in order.

The replay result is the canonical current state.

In v1, Penny should assume full replay from the vault on startup. Derived local caches or projections may be added later, but they are not the source of truth.

### Log Entry Types

Most mutations are stored as JSON records.

Example:

```json
{
  "schema_version": 1,
  "type": "balance_snapshot_added",
  "timestamp": "2026-04-04T14:22:11Z",
  "account_id": 3,
  "subaccount_type": "giro",
  "snapshot_date": "2026-04-04",
  "balance_cents": 182340
}
```

Some mutations need richer artifacts than a single JSON object.

#### Import Mutations

Imports are stored as directories:

```text
000003_import_comdirect/
  event.json
  source.csv
  transactions.jsonl
```

This preserves:

- the original raw file
- the import metadata
- the normalized parsed result at the time of import

The normalized parsed result is persisted so that future parser changes do not alter historical replay.

#### Rules Mutations

Rules changes are also mutations.

When the user uploads or saves a new rules version, Penny persists it as a numbered Python file, for example:

```text
000023_rules.py
```

Replay semantics:

- the latest `*_rules.py` file in log order becomes the active rules source
- old rule versions remain available for audit and history

This keeps rules human-readable and preserves the exact classifier code that was active at a given point in the mutation history.

### Compatibility Contract

The compatibility boundary is the mutation log format.

Penny must remain backwards-compatible at the replay layer:

- old log entries must continue to replay correctly
- entries declare a `schema_version`
- new features should add new record types or new schema versions
- Penny must not silently reinterpret old records in incompatible ways

### Internal Database Role

SQLite is not the source of truth.

If SQLite is used internally, it is a derived projection built from replay.

That means:

- deleting the internal database must not lose user state
- the database can always be recreated from the vault
- copying the vault is sufficient for backup and migration

### Naming Convention

Log entries use:

- a monotonic numeric prefix for ordering
- a descriptive suffix for readability

Examples:

```text
000001_init.json
000002_account_created.json
000003_import_comdirect/
000004_balance_snapshot_added.json
000023_rules.py
```

The numeric prefix is the ordering mechanism; the suffix is descriptive only.

## Consequences

- Penny becomes portable by copying one user-owned directory
- backups are straightforward
- rules, imports, and manual edits become auditable history
- rebuilding state on a new laptop becomes deterministic
- internal SQLite state is no longer opaque or critical

## Out of Scope

- compression or archival policies for old imports
- cross-machine sync protocol
- projection caching strategy beyond the replay model
- cryptographic signing of log entries

## References

- ADR-007: Transaction Parsing
- ADR-008: Transaction Classification
- ADR-009: Account Balance Snapshots
