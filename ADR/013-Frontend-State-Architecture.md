# ADR-013: Frontend State Architecture

## Status
Accepted

## Context
The frontend mixed several incompatible state patterns:

- global selectors lived partly in the root and partly in views
- views mutated backend state directly
- invalidation after writes was inconsistent
- stale data remained visible after imports, rules changes, and rebuilds

At the same time, the frontend must not be designed as a copy of the database.
The backend already owns the data and computes read models through SQL-backed
REST endpoints.

## Decision
Use a split model:

- `app.js` owns global selector state, mutations, and invalidation
- views own localized read loading for their own read models

## Design

### 1. `app.js` owns global selector state

`app.js` owns the shared state that changes the meaning of many queries:

- active view and tab
- date range
- selected accounts
- search text
- selected category
- URL-synced navigation state

This is the shared query context of the application.

### 2. `app.js` owns mutations

All UI-triggered writes are initiated from `app.js`.

Examples:

- imports and demo import
- rebuilds
- account updates and archive actions
- balance snapshot writes
- rules save
- rules run

Views may trigger these actions, but they do not implement the write logic
themselves.

### 3. `app.js` owns invalidation

`app.js` keeps a frontend invalidation counter such as `dbRevision`.

After every successful mutation, `app.js` increments that counter.

This counter is part of the dependency set for all read queries.

### 4. Views own read loading

Views may load their own read models from the backend.

That includes:

- issuing read requests
- managing loading and error state
- caching the latest response for rendering

This logic should stay as local to the view as possible.

Examples:

- transactions view loads transactions
- report view loads report data
- balance view loads balance history
- rules view loads rules status and latest run

### 5. Views treat read data as stale on argument changes

View-owned read state must be refreshed whenever any query argument changes.

That includes:

- relevant global selector state from `app.js`
- view-local query arguments
- the root invalidation counter

In practice, view reads depend on a tuple like:

`(global selectors, local view args, dbRevision)`

### 6. Query results are cached read models

Frontend datasets are not canonical application state.

They are cached results of backend queries used for rendering.

The backend remains the source of truth for computed data such as:

- transactions
- reports
- balance history
- account summaries
- rules status and classification results
- import history

### 7. Local UI state stays local

Views may keep purely local presentation state, such as:

- pagination
- drafts
- expanded and collapsed sections
- hover or drag state
- temporary local selection

Do not move this state to `app.js` unless it becomes shared state or part of
query semantics.

### 8. No DB-managed invalidation for now

The invalidation counter lives in `app.js`, not in the database.

Rationale:

- writes currently flow through the UI
- the UI can invalidate immediately after a successful mutation
- a DB-side counter would not notify the browser on its own
- polling, SSE, websockets, and cross-process sync are out of scope for now

If the product later needs multi-tab or external-writer awareness, this
decision should be revisited.

## Architecture

```text
global selectors + mutations + dbRevision
                 │
                 ▼
              app.js
                 │
       passes selectors/actions down
                 │
                 ▼
      view-local read loading and caching
                 │
                 ▼
      backend REST endpoints / SQL read models
```

## Rules

1. Global selector state lives in `app.js`.
2. UI-triggered writes are initiated from `app.js`.
3. Successful writes increment the root invalidation counter.
4. Views may load their own read models.
5. View reads must refresh when selectors, local query args, or `dbRevision`
   change.
6. Query results are cached read models, not a copy of the database.
7. View-local presentation state stays local by default.

## Consequences

### Positive

- writes and invalidation have one clear owner
- read logic stays close to the view that needs it
- views can remain simple without pretending the root owns all data
- stale data rules become explicit through `dbRevision`
- SQL and REST remain visible as the source of computed truth

### Negative

- each view must correctly declare and react to its read dependencies
- invalidation bugs can still happen if a view forgets to depend on
  `dbRevision`
- out-of-band backend writes are not observed automatically
