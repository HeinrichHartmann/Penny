# Code Review: Penny UI Enhancement Session
**Date:** 2026-04-04
**Reviewer:** Claude Opus 4.5
**Scope:** Rules editor, classification log, search improvements

---

## Summary

This session added three major features to the Penny UI:
1. **Rules Editor** with save/reload and XDG path compliance
2. **Classification Log** with stats, error reporting, and unmatched transaction listing
3. **Client-side Search** with full-text matching across all transaction fields

**Lines Changed:** +333 / -18 across 5 files

---

## Changes by File

### `src/penny/server.py` (+136 lines)

#### New Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/rules` | GET | Fetch rules.py content and path |
| `/api/rules` | PUT | Save rules.py content |
| `/api/rules/run` | POST | Run classification and return stats/logs |

#### Code Quality

**Strengths:**
- Clean separation of concerns (rules loading, classification, storage)
- Comprehensive error handling with syntax error line numbers
- Structured logging with levels (info, warning, error, debug)

**Areas for Improvement:**
```python
# Line 480: Type hint issue - list_transactions accepts Optional[int], not None directly
transactions = tx_storage.list_transactions(limit=None)
# Consider: transactions = tx_storage.list_transactions()
```

```python
# Line 505: Unused variable
matched_count, db_unmatched_count = tx_storage.apply_classifications(decisions)
# Consider: matched_count, _ = tx_storage.apply_classifications(decisions)
```

**Security Consideration:**
- `MINIMAL_RULES_TEMPLATE` is written to disk when rules.py doesn't exist
- The rules file is executed as Python code via `load_rules()`
- Recommendation: Consider sandboxing or validation before execution

---

### `src/penny/static/app.js` (+67 lines)

#### New Features
- `runClassification()` - triggers classification and updates log state
- `filteredTransactions` - client-side search computed property
- `filteredTransactionCount` - reactive count for pagination

#### Code Quality

**Strengths:**
- Clean reactive state management with Vue composition API
- Efficient client-side filtering (no server round-trips for search)
- Proper pagination reset on search query change

**Refactoring Opportunity:**
```javascript
// Lines 315-327: Field list could be extracted as constant
const SEARCHABLE_FIELDS = ['description', 'category', 'account', 'raw_description', 'merchant', 'booking_date'];

const filteredTransactions = computed(() => {
  const rows = transactions.value?.transactions || [];
  const q = searchQuery.value?.toLowerCase().trim();
  if (!q) return rows;

  return rows.filter((tx) => {
    const searchable = SEARCHABLE_FIELDS
      .map(f => tx[f])
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return searchable.includes(q);
  });
});
```

---

### `src/penny/static/index.html` (+70 lines)

#### New UI Components
1. **Classification Log Panel** - stats summary + scrollable log viewer
2. **Run Classification Button** - manual trigger
3. **Enhanced Pagination** - shows filtered vs total count

#### Code Quality

**Strengths:**
- Good use of Vue conditional rendering
- Color-coded log levels (error=red, warning=yellow, info=white, debug=gray)
- Responsive stats grid

**Accessibility:**
- Log panel has good contrast (dark bg #1a1a1a, light text #ccc)
- Consider adding `role="log"` and `aria-live="polite"` for screen readers

---

### `src/penny/static/api.js` (+11 lines)

#### New Functions
- `runRules()` - POST to `/api/rules/run`

**Code Quality:** Clean, consistent with existing patterns.

---

### `rules.py` (+67 lines)

#### New Classification Rules
| Category | Rules Added |
|----------|-------------|
| `professional/coaching` | Johannes Metzler, Ankush Jain |
| `investment/currency` | Devisen |
| `transfer/family` | Lena Hartmann Heinrich Hartmann |
| `personal/whiskey` | Richelle Dangremond |
| `shopping/electronics` | Media Markt, Saturn |
| `travel/refund` | Service-now.com |
| `transport/car` | Fred Wehrmann |
| `travel/vacation` | Hof-Ferien, Medewege |
| `family/childcare` | Diakoniewerk |
| `shopping/bicycle` | Fahrrad Lohmeier |
| `shopping/jewelry` | Juwelier |

#### Updated Rules
- `household/home_improvement` - added Tischlerei Becker
- `insurance` - added Verti Versicherung
- `food/restaurants` - added Extrablatt

**Impact:** Match rate improved from 0% to 89.6% (3,621 of 4,040 transactions)

---

## Architecture Notes

### Data Flow
```
User edits rules.py in UI
        ↓
PUT /api/rules (save to ~/.local/share/penny/rules.py)
        ↓
POST /api/rules/run
        ↓
load_rules() → LoadedRuleset
        ↓
Classify all transactions
        ↓
apply_classifications() → Update DB
        ↓
Return logs + stats to UI
```

### XDG Compliance
- Database: `~/.local/share/penny/penny.db` ✓
- Rules: `~/.local/share/penny/rules.py` ✓
- Respects `PENNY_DATA_DIR` environment variable ✓

---

## Testing Recommendations

### Manual Testing
- [ ] Save rules with syntax error → verify error message shows line number
- [ ] Search for "uncategorized" → verify 419 results
- [ ] Search for partial text (e.g., "zalando") → verify matches in all fields
- [ ] Run classification → verify stats update and logs scroll

### Unit Tests Needed
```python
# tests/test_server.py
def test_rules_run_syntax_error():
    """POST /api/rules/run with invalid Python returns error with line number"""

def test_rules_run_classification_stats():
    """POST /api/rules/run returns correct matched/unmatched counts"""

def test_search_concatenated_fields():
    """Search matches across payee, memo, raw_buchungstext, etc."""
```

---

## Performance Considerations

1. **Classification runs on ALL transactions** - O(n * r) where n=transactions, r=rules
   - Current: 4,040 transactions × 80 rules ≈ 0.06s (acceptable)
   - At scale: Consider incremental classification for new transactions only

2. **Client-side search** - O(n) filter on every keystroke
   - Current: 4,040 transactions (acceptable)
   - At scale: Consider debouncing or virtual scrolling

---

## Commits Ready

```bash
git add -A
git commit -m "Add Rules editor with classification log and client-side search

- Rules view: edit, save, reload rules.py from XDG data directory
- Classification: run button, stats panel, error/warning logs
- Search: client-side filtering across all transaction fields
- New rules: 80 total, 89.6% match rate (3621/4040)

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Next Steps (Suggested)

1. **Fingerprint-based rules** - for one-off transactions like whiskey purchases
2. **Rule testing** - preview matches before saving
3. **Category autocomplete** - suggest existing categories when writing rules
4. **Incremental classification** - only classify new/modified transactions

---

## Design Note: Transfer Neutralization

**Current State:** Neutralization is disabled. Internal transfers double-count in totals.

### Proposed Solution: Inferred Transaction IDs

Every transaction entry gets a `transaction_id`. Entries sharing the same ID represent two sides of one logical transaction (ledger semantics).

#### Core Principle: View-Dependent Neutralization

```
Selection = Entity Boundary

┌─────────────────────────────────────┐
│  Selected Accounts (your "entity") │
│                                     │
│   Account A ──────► Account B       │  ← Internal edge (neutralized)
│       │                             │
│       ▼                             │
└───────┼─────────────────────────────┘
        │
        ▼
   External World                        ← External edge (visible)
```

**The Rule:**
- Both sides of `transaction_id` **inside** selection → neutralize (internal transfer)
- Only one side inside selection → show it (external flow)

This matches consolidated accounting: subsidiaries eliminate inter-company transactions.

#### Inference Logic
```
Match candidates where:
  - abs(amount_a) == abs(amount_b)
  - sign(amount_a) != sign(amount_b)
  - account_a != account_b
  - abs(date_a - date_b) <= 2 days

transaction_id = deterministic_hash(amount, date_bucket, sorted_accounts)
```

#### Schema Change
```sql
ALTER TABLE transactions ADD COLUMN transaction_id TEXT;
CREATE INDEX idx_transactions_txid ON transactions(transaction_id);
```

#### Query Logic (Pseudocode)
```python
def get_visible_transactions(selected_account_ids, all_transactions):
    # Group by transaction_id
    groups = group_by(all_transactions, key=lambda t: t.transaction_id)

    visible = []
    for txid, entries in groups.items():
        accounts_in_selection = [e for e in entries if e.account_id in selected_account_ids]
        accounts_outside = [e for e in entries if e.account_id not in selected_account_ids]

        if len(accounts_in_selection) == 1:
            # Only one side in view → external flow, show it
            visible.extend(accounts_in_selection)
        elif len(accounts_in_selection) > 1 and len(accounts_outside) == 0:
            # All sides internal → neutralize (hide all)
            pass  # or show with "neutralized" flag for UI toggle
        else:
            # Mixed: some in, some out → show the in-selection ones
            visible.extend(accounts_in_selection)

    return visible
```

#### UI Behavior
| Selection | Behavior |
|-----------|----------|
| Single account | Show all (every tx is external to that account) |
| Subset of accounts | Neutralize internal, show external |
| All accounts | Neutralize all internal transfers |

#### UI Enhancements
- Toggle: "Show neutralized transfers" (dimmed, linked visually)
- Neutralized pairs share color/icon
- Hover on one side highlights the other

#### Edge Cases
- **Partial transfers** (€1000 out → €500 + €500 in): Multiple transaction_ids, or N:M matching
- **Same-day coincidence**: Manual override to un-link false matches
- **Cross-currency**: Match on transaction date + reference, not amount
- **N-way splits**: One transaction_id can have >2 entries
