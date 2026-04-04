# ADR-009: Transfer Neutralization

## Status
Draft

## Context

Bank transactions are single-entry records: each account shows its own view of a transfer. When viewing multiple accounts together, internal transfers appear twice:

```
Account A: -500 €  (outgoing)
Account B: +500 €  (incoming)
```

This double-counts in totals and clutters the transaction list. The problem extends beyond simple transfers to complex operations like portfolio consolidations:

```
Portfolio rebalance (7 entries):
  -1000 € (sell A)
  -500 €  (sell B)
  +800 €  (buy C)
  +600 €  (buy D)
  +50 €   (dividend)
  -20 €   (fee)
  +100 €  (settlement)
  ─────────────────
  Net: +30 €
```

These entries represent ONE logical transaction with multiple legs.

## Decision

### Core Model: Transaction Groups

Introduce `transaction_id` to group entries that belong to the same logical transaction.

```sql
ALTER TABLE transactions ADD COLUMN transaction_id TEXT;
CREATE INDEX idx_transactions_txid ON transactions(transaction_id);
```

Entries sharing the same `transaction_id` are legs of one transaction.

### Neutralization = Aggregation

Neutralization does NOT mean hiding. It means **consolidating entries to their net sum**.

| View | Behavior |
|------|----------|
| Single account | Show raw entries (atomic view for that account) |
| Multiple accounts | Show consolidated `transaction_id` groups with net sum |

A "neutralized" transaction is the **sum of its entries**:
- Simple transfer: net €0 (may be hidden or shown dimmed)
- Portfolio rebalance: net +€30 (shown as single line)
- Transfer with fee: net -€2 (the fee is visible)

### Inference Logic

Transaction groups are inferred through multiple strategies, in order of confidence:

#### 1. Reference Match (High Confidence)
```
Same `reference` field across entries
+ opposite signs
+ different accounts
→ Link automatically
```

Banks often use the same reference number on both sides of a transfer.

#### 2. Amount + Date Match (Medium Confidence)
```
abs(amount_a) == abs(amount_b)
+ sign(amount_a) != sign(amount_b)
+ account_a != account_b
+ abs(date_a - date_b) <= 2 days
→ Surface as candidate for confirmation
```

#### 3. Classification Hint (Medium Confidence)
```
Both entries classified as transfer/*
+ amount/date match criteria
→ Surface as candidate for confirmation
```

#### 4. Manual Link (Explicit)
User explicitly groups entries via UI.

### Transaction ID Generation

For automatic matches:
```python
transaction_id = sha256(
    sorted([entry_a.fingerprint, entry_b.fingerprint])
).hexdigest()[:16]
```

For manual links, generate a new UUID-based ID.

### Workflow

1. **Auto-link** high-confidence matches (reference-based)
2. **Surface candidates** for user review (amount+date matches)
3. **Allow manual linking** in transaction detail view
4. **Store confirmed links** as `transaction_id`

This runs as a batch operation, similar to classification:
```bash
penny link-transfers
```

Or via the web UI "Detect Transfers" button.

### Query Logic

```python
def get_transactions(selected_account_ids, consolidate=True):
    all_txns = fetch_transactions(selected_account_ids)

    if not consolidate or len(selected_account_ids) == 1:
        return all_txns  # Raw entries

    # Group by transaction_id
    groups = defaultdict(list)
    ungrouped = []
    for tx in all_txns:
        if tx.transaction_id:
            groups[tx.transaction_id].append(tx)
        else:
            ungrouped.append(tx)

    result = ungrouped[:]
    for txid, entries in groups.items():
        # Check if all legs are within selection
        in_selection = [e for e in entries if e.account_id in selected_account_ids]

        if len(in_selection) > 1:
            # Multiple legs in view → consolidate to net
            result.append(ConsolidatedTransaction(
                transaction_id=txid,
                amount_cents=sum(e.amount_cents for e in in_selection),
                entries=in_selection,
                # Use earliest date, combine descriptions, etc.
            ))
        else:
            # Only one leg in view → show as-is
            result.extend(in_selection)

    return result
```

### UI Exposure

#### Transactions View
- Toggle: "Consolidate transfers" (default ON for multi-account view)
- Consolidated rows show:
  - Net amount
  - Entry count badge: "(3 entries)"
  - Expandable to show individual legs

#### Transaction Detail
- Shows all linked entries
- "Link with..." action to manually group
- "Unlink" action to break a group

#### Classification Log
- Reports: "X transfer groups detected (Y auto-linked, Z candidates)"

### Persistence

```sql
-- transactions table
transaction_id TEXT,  -- NULL = ungrouped, shared value = grouped

-- Optional: explicit link table for complex cases
CREATE TABLE transaction_links (
    id INTEGER PRIMARY KEY,
    transaction_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL REFERENCES transactions(fingerprint),
    linked_at TEXT NOT NULL,
    linked_by TEXT  -- 'auto:reference', 'auto:amount_date', 'manual'
);
```

For v1, the column-based approach is sufficient. The link table can be added later for audit trails.

## Consequences

- Internal transfers no longer double-count in totals
- Portfolio consolidations appear as single net transactions
- Fees and partial transfers are correctly accounted (non-zero net)
- Single-account view remains unchanged (raw entries)
- Users can review and correct inferred links

## Edge Cases

| Case | Handling |
|------|----------|
| Partial transfer (€1000 → €500 + €500) | Multiple transaction_ids, or N:M matching in v2 |
| Same-day coincidence (rent out, salary in) | Amount+date match surfaces as candidate, not auto-linked |
| Cross-currency transfer | Match on reference + date, not amount |
| N-way splits | One transaction_id can have >2 entries |
| Fee as separate entry | Include in group if same reference/date |

## Out of Scope (v1)

- Automatic fee detection and grouping
- Cross-currency amount matching
- Predictive linking ("this looks like your usual savings transfer")
- Undo/redo for manual links

## References

- ADR-008: Transaction Classification
- Prior art: FinanceAnalysis `neutralize.py` (same-as rules approach)
