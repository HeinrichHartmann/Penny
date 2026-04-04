# ADR-009: Transfer Neutralization

## Status
Draft

## Context

Bank exports contain single-entry records: each account shows its own view of a transfer. When viewing multiple accounts together, internal transfers appear twice:

```
Account A: -500 €  (outgoing)
Account B: +500 €  (incoming)
```

This double-counts in totals and clutters the view. The problem extends beyond simple transfers to complex operations like portfolio consolidations:

```
Portfolio rebalance (124 entries):
  -1000 € (sell A)
  -500 €  (sell B)
  +800 €  (buy C)
  +600 €  (buy D)
  ... 120 more entries ...
  ─────────────────
  Net: -10,023,231 €
```

These entries represent ONE logical transaction with multiple legs. Note: the amounts do NOT balance to zero, and there is no amount-based correlation between entries.

### Terminology

- **Entry**: A single row in the bank export (what we store in `transactions` table)
- **Transfer group**: Multiple entries that belong to the same logical transaction
- **Neutralization**: Aggregating a transfer group to its net sum

## Decision

### User-Defined Grouping via `rules.py`

Transfer grouping is defined by the user in `rules.py`, similar to classification. The user provides:

```python
# rules.py

# Config: which entries to consider
TRANSFER_PREFIX = "transfer/"
TRANSFER_WINDOW_DAYS = 10

# Predicate: are these two entries part of the same transfer?
def in_same_transfer_group(a: Entry, b: Entry) -> bool:
    """Pure symmetric predicate. Return True if a and b belong together."""

    # Investment entries within same week cluster together
    if "investment" in a.category and "investment" in b.category:
        return True

    # Card settlement
    if "VISA" in a.raw_buchungstext and "VISA" in b.raw_buchungstext:
        return True

    # Simple internal transfer (opposite amounts, different accounts)
    if a.amount_cents == -b.amount_cents and a.account_id != b.account_id:
        return True

    return False
```

### System-Provided Optimization

The system handles performance optimization internally:

1. **Pre-filter** by `TRANSFER_PREFIX` (only `transfer/*` entries considered)
2. **Sort** by date
3. **Sliding window** of `TRANSFER_WINDOW_DAYS` (only compare nearby entries)
4. **Union-Find** for transitive closure

This reduces complexity from O(n²) to O(n × w) where w = window size.

```
100,000 total entries
  → 10,000 transfer/* entries (after prefix filter)
  → 10,000 × 100 = 1M comparisons (with 10-day window)
  → ~1 second runtime ✓
```

### Algorithm

```python
def link_transfers(entries, predicate, prefix, window_days):
    # 1. Pre-filter by category prefix
    transfers = [e for e in entries if e.category.startswith(prefix)]

    # 2. Sort by date
    transfers.sort(key=lambda e: e.date)

    # 3. Sliding window comparison
    groups = UnionFind()
    for i, a in enumerate(transfers):
        for j in range(i + 1, len(transfers)):
            b = transfers[j]
            if (b.date - a.date).days > window_days:
                break  # Sorted, no more candidates
            if predicate(a, b):
                groups.union(a.fingerprint, b.fingerprint)

    # 4. Assign transaction_id from groups
    return groups.to_transaction_ids()
```

### Schema

```sql
ALTER TABLE transactions ADD COLUMN transaction_id TEXT;
CREATE INDEX idx_transactions_txid ON transactions(transaction_id);
```

- `NULL` = ungrouped entry
- Shared value = entries belong to same transfer group

### Neutralization = Aggregation

Neutralization does NOT mean hiding. It means **consolidating entries to their net sum**.

| View | Behavior |
|------|----------|
| Single account | Show raw entries (atomic view for that account) |
| Multiple accounts | Show consolidated groups with net sum |

A "neutralized" transfer group is the **sum of its entries**:
- Simple transfer: net €0 (may be hidden or shown dimmed)
- Portfolio rebalance: net -€10M (shown as single line)
- Transfer with fee: net -€2 (the fee is visible)

### Query Logic

```python
def get_entries(selected_account_ids, consolidate=True):
    all_entries = fetch_entries(selected_account_ids)

    if not consolidate or len(selected_account_ids) == 1:
        return all_entries  # Raw entries

    # Group by transaction_id
    groups = defaultdict(list)
    ungrouped = []
    for e in all_entries:
        if e.transaction_id:
            groups[e.transaction_id].append(e)
        else:
            ungrouped.append(e)

    result = ungrouped[:]
    for txid, entries in groups.items():
        in_selection = [e for e in entries if e.account_id in selected_account_ids]

        if len(in_selection) > 1:
            # Multiple legs in view → consolidate to net
            result.append(ConsolidatedEntry(
                transaction_id=txid,
                amount_cents=sum(e.amount_cents for e in in_selection),
                entries=in_selection,
                date=min(e.date for e in in_selection),
            ))
        else:
            # Only one leg in view → show as-is
            result.extend(in_selection)

    return result
```

### Workflow

1. User classifies entries (some get `transfer/*` category)
2. User defines `in_same_transfer_group()` in `rules.py`
3. Run linking: `penny link-transfers` or UI button
4. System assigns `transaction_id` to grouped entries
5. Views show consolidated groups

### CLI

```bash
penny link-transfers [--dry-run]
```

Output:
```
Loaded rules: ~/.local/share/penny/rules.py
  TRANSFER_PREFIX = "transfer/"
  TRANSFER_WINDOW_DAYS = 10

Entries: 4,040 total, 892 transfers
Groups found: 234
  - 180 pairs (2 entries each)
  - 42 triplets
  - 12 larger groups (max 124 entries)

Linked: 534 entries into 234 groups
```

### UI

- **Transactions view**: Toggle "Consolidate transfers" (default ON for multi-account)
- **Consolidated row**: Shows net amount, "(N entries)" badge, expandable
- **Detail view**: Shows all linked entries

## Consequences

- User has full control over grouping logic
- No magic amount-matching heuristics
- Portfolio consolidations (N entries, arbitrary amounts) work correctly
- System handles performance optimization transparently
- Classification must happen before linking

## Out of Scope (v1)

- Manual link/unlink in UI (user edits `rules.py` instead)
- Undo/redo for linking
- Cross-currency matching

## References

- ADR-008: Transaction Classification
- Prior art: FinanceAnalysis `neutralize.py`
