# Current Task: Balance Chart Improvements

## Goal
Improve the Balance View chart to show clearer daily balance changes with interactive date range selection.

## Requirements

### Backend (Python)
- [x] Aggregate balance data to **one point per day** in API endpoint
- [x] Return end-of-day balance for each date
- [x] No transaction-level granularity (date-only, no time)
- [x] Add comment: "ALL MATH MUST BE DONE IN THE BACKEND"

### Frontend (JavaScript)
- [ ] Display **stepped line chart** (`step: 'end'`) - balance stays flat until next transaction day
- [ ] Remove all data points/circles (no symbols)
- [ ] Add **horizontal brush selection** for date range zooming
  - [ ] Always active (no toggle buttons)
  - [ ] Drag horizontally on chart to select date range
  - [ ] Sync selection to global date filters (updates other views)
  - [ ] Hide toolbox controls (no reset/zoom buttons)
- [ ] Use time-based x-axis (not category-based)

## Current Issue
The chart is NOT displaying correctly:
- Chart may not be stepped (need to verify)
- Brush selection may not be working
- Need to debug why changes aren't taking effect

## Files Modified
- `src/penny/api/dashboard.py` - Backend aggregation to daily data
- `src/penny/static/views/balance.js` - Chart configuration
- `src/penny/static/views/BalanceView.js` - View component
- `src/penny/static/app.js` - Date filter sync

## Testing Checklist
- [ ] Chart displays stepped lines (horizontal steps between days)
- [ ] No data point symbols visible
- [ ] Horizontal brush selection works (drag to select range)
- [ ] Date range updates in header after selection
- [ ] Other views (transactions, etc.) update when date range changes
- [ ] No console errors
- [ ] All tests pass (`make test`)
- [ ] Lint passes (`make lint`)

## Notes
- Bank CSVs only provide date (not datetime), so daily aggregation is correct
- Comdirect embeds timestamps in transaction descriptions, but we ignore them
- Frontend must do NO math - only display data 1:1 from backend

---

## CORRECTED Balance Calculation Logic (2026-04-05)

### Step 1: Raw Transaction History
- Get **raw, unneutralized** transaction logs for each account
- No transfer grouping/neutralization at this stage
- Work with the FULL transaction history for each account (not filtered by date range)

### Step 2: Daily Aggregation
- **Bucket transactions by day** to get daily saldo (net change per day)
- Create **date-indexed arrays** from first to last available data point
- Result: ~3K entries max (1-10 years of daily data) - very manageable in memory

### Step 3: Balance Anchor Projection
For each account, using **ALL** balance anchors across the entire time range:

- **Balance anchors project BACKWARDS** (not forwards!)
- **Exception**: The **last (most recent) anchor projects FORWARD** to today/latest date
- Example with anchors on Jan 1, June 1, Dec 1:
  - Dec 1 (last anchor) → projects **forward** to today/latest date
  - June 1 → projects **backward** from June 1 to Jan 2
  - Jan 1 → projects **backward** from Jan 1 to start of data

**Projection Math:**
- Backward: `balance[date] = anchor_balance - sum(saldo[date+1 to anchor_date])`
- Forward (last anchor only): `balance[date] = anchor_balance + sum(saldo[anchor_date+1 to date])`

### Step 4: Visualization
- **Mark balance anchors with FAT dots** on the chart (larger symbols at anchor dates)
- **Show unexplained delta** when projections from consecutive anchors don't match
  - Detect: backward projection from anchor N ≠ forward projection from anchor N-1
  - This indicates data inconsistency (missing transactions, incorrect snapshot, etc.)
  - Display warning/indicator to user

### Why This Approach?
- Balance snapshots are typically entered "looking at today's balance" and anchoring history backwards
- Most recent snapshot should project to current day (latest balance)
- Inconsistencies reveal data quality issues (missing imports, manual edits, etc.)
