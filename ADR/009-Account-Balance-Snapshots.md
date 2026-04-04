# ADR-009: Account Balance Snapshots

## Status
Draft

## Context

Issue #2 adds two related requirements to the Accounts view:

- users must be able to edit account metadata after import
- users must be able to record balances for an account at specific dates

The current account model already includes:

```python
balance_cents: int | None
balance_date: date | None
```

Those fields are sufficient for a single "latest known balance" value, but they are not sufficient for balance history:

- they only store one point in time
- they do not support multiple manual balance records
- they do not support per-subaccount balances
- they make it harder to distinguish user-entered balances from derived balances

Penny already persists account state in SQLite. So balance snapshots should also be persisted in SQLite, not only in transient frontend state.

## Decision

### Separate Snapshot Records

Balance history is stored as separate snapshot records, not as repeated edits to fields on `accounts`.

The source of truth is a dedicated `account_balance_snapshots` table.

```sql
CREATE TABLE account_balance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    subaccount_type TEXT NOT NULL DEFAULT '',
    snapshot_date TEXT NOT NULL,
    balance_cents INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'EUR',
    source TEXT NOT NULL DEFAULT 'manual',
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, subaccount_type, snapshot_date, source)
);

CREATE INDEX idx_balance_snapshots_account
    ON account_balance_snapshots(account_id);

CREATE INDEX idx_balance_snapshots_account_date
    ON account_balance_snapshots(account_id, subaccount_type, snapshot_date DESC);
```

### Scope Model

Snapshots support both whole-account and subaccount balances in one table.

- `subaccount_type = ''` means the snapshot applies to the whole account
- `subaccount_type = 'giro' | 'visa' | 'tagesgeld' | 'depot'` means the snapshot applies to a specific subaccount

This keeps the model simple and avoids a second snapshot table.

### Account Model Semantics

The `accounts` table remains the place for editable account metadata:

- `display_name`
- `iban`
- `holder`
- `notes`

The current `accounts.balance_cents` and `accounts.balance_date` fields are treated as convenience fields only.

If retained, they represent:

- the latest known whole-account balance snapshot
- cached for quick display in the Accounts view

They are not the canonical history store.

### UI Model

The Accounts view should support two separate editing flows on each account card:

1. Metadata editing
   - display name
   - IBAN
   - holder
   - notes

2. Balance snapshot editing
   - add snapshot
   - edit snapshot
   - delete snapshot

Each account card should show:

- account identity and bank metadata
- latest balance snapshot, if present
- latest snapshot date
- known subaccounts
- a balance history list or drawer

The add/edit balance flow should capture:

- `snapshot_date`
- `balance_cents`
- `subaccount_type`
- optional `note`

### API Shape

Accounts metadata remains under the existing account endpoints.

Balance snapshots should get explicit endpoints, for example:

```text
GET    /api/accounts/{account_id}/balance-snapshots
POST   /api/accounts/{account_id}/balance-snapshots
PATCH  /api/accounts/{account_id}/balance-snapshots/{snapshot_id}
DELETE /api/accounts/{account_id}/balance-snapshots/{snapshot_id}
```

This keeps account metadata updates separate from historical balance operations.

### Current Balance Computation

Penny may compute a displayed "current balance" from:

- the latest applicable snapshot
- plus transaction deltas after the snapshot date

But that computed view is downstream of the snapshot records.

Snapshot storage itself stays simple and manual-first.

### Migration Strategy

If `accounts.balance_cents` and `accounts.balance_date` already contain data, migration should:

1. create one whole-account snapshot row from those fields
2. preserve the original values
3. optionally continue updating them as the cache of the latest whole-account snapshot

## Consequences

- Balance history becomes first-class data instead of a single mutable field
- Whole-account and subaccount balances share one model
- The Accounts UI can show editable balance history cleanly
- Future import or computed balance sources can reuse the same snapshot table
- The current account table remains focused on account metadata

## Out of Scope

- automatic balance derivation from bank APIs
- portfolio valuation for securities positions
- balance visualization and charts
- reconciliation workflows across multiple snapshots

## References

- Issue #2: `Support editing account metadata and balance snapshots in the Accounts view`
- ADR-005: Account Register
