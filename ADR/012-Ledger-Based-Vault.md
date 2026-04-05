# ADR-012: Ledger-Based Vault with history.tsv

**Status:** Proposed
**Date:** 2024-04-05
**Supersedes:** ADR-010 (Portable Event Log Storage)

## Context

The current vault uses directory-based event log storage:

```
~/Documents/Penny/
  imports/
    000001-ingest_sparkasse/
      manifest.json
      file.CSV
    000002-rules/
      manifest.json
      rules.py
    000003-balance_snapshot/
      manifest.json
```

**Problems:**
1. **No single source of truth** - Must scan directories to find entries
2. **No easy disable/delete** - Can't skip entries without deleting files
3. **Slow replay** - Must iterate directories, parse filenames, read manifests
4. **Poor organization** - All entry types mixed in one directory
5. **Implicit ordering** - Sequence only in directory names

## Decision

Replace directory-based log with **ledger-based vault** using `history.tsv` as the single source of truth.

### New Structure

```
~/Documents/Penny/
  penny.db                          # SQLite projection (derived state)
  history.tsv                       # Master ledger (source of truth)

  rules/
    0001_2024-01-15T12:00:00Z_rules.py
    0005_2024-03-20T14:30:00Z_rules.py

  balance/
    0002_2024-02-10T09:15:00Z_balance.tsv

  transactions/
    0003_2024-02-15T10:20:00Z/
      original-filename.CSV
      manifest.json
    0004_2024-03-01T15:45:00Z/
      another-file.CSV
      manifest.json
```

### history.tsv Format

Tab-separated values with 3 columns:

```tsv
seq	mutation-type	mutation-record
0001	rules-import	{"timestamp":"2024-01-15T12:00:00Z","filename":"rules.py"}
0002	balance-import	{"timestamp":"2024-02-10T09:15:00Z","filename":"balance.tsv","count":5}
0003	ingest	{"timestamp":"2024-02-15T10:20:00Z","parser":"sparkasse","csv_files":["file.CSV"],"status":"applied","enabled":true}
0004	ingest	{"timestamp":"2024-03-01T15:45:00Z","parser":"sparkasse","csv_files":["multi.CSV"],"status":"applied","enabled":false}
```

**Columns:**
- `seq` - 4-digit sequence number (0001, 0002, ...) - matches filename prefixes
- `mutation-type` - Entry type (`ingest`, `rules-import`, `balance-import`, `account_created`, etc.)
- `mutation-record` - JSON object with entry metadata

### File Organization

**Rules:** `rules/{seq}_{timestamp}_rules.py`
- Timestamped for easy identification
- Filename includes sequence for correlation with history.tsv
- Example: `0001_2024-01-15T12:00:00Z_rules.py`

**Balance Snapshots:** `balance/{seq}_{timestamp}_balance.tsv`
- TSV format (account_iban, date, balance_cents, note)
- Example: `0002_2024-02-10T09:15:00Z_balance.tsv`

**Transaction Imports:** `transactions/{seq}_{timestamp}/`
- Directory per import (may contain multiple CSV files)
- Preserves original filenames
- Includes manifest.json with parser metadata
- Example: `0003_2024-02-15T10:20:00Z/20240215-12345-umsatz.CSV`

### Replay Algorithm

```python
def replay_vault():
    """Rebuild penny.db from history.tsv"""
    init_db()  # Create empty schema

    for line in read_tsv("history.tsv"):
        seq, mutation_type, record = parse_line(line)

        if mutation_type == "ingest":
            if record["enabled"]:  # Can skip disabled entries
                csv_dir = f"transactions/{seq}_{record['timestamp']}"
                apply_ingest(csv_dir, record)

        elif mutation_type == "rules-import":
            rules_file = f"rules/{seq}_{record['timestamp']}_rules.py"
            load_rules(rules_file)

        elif mutation_type == "balance-import":
            balance_file = f"balance/{seq}_{record['timestamp']}_balance.tsv"
            apply_balance_snapshots(balance_file)

        # ... other mutation types
```

### Enabling/Disabling Imports

**Disable an import:**
1. Edit history.tsv
2. Update mutation-record: `"enabled":false`
3. Run `penny db rebuild`

**Remove an import:**
1. Delete line from history.tsv
2. Run `penny db rebuild`
3. (Optionally) delete files from transactions/

**Note:** Files can remain in vault directories even if removed from history.tsv - they'll be ignored during replay.

## Benefits

1. **Single source of truth** - history.tsv explicitly lists all mutations in order
2. **Fast replay** - Single file read, no directory scanning
3. **Easy disable** - Edit JSON record, set `"enabled":false`
4. **Easy delete** - Remove line from history.tsv
5. **Better organization** - Files grouped by type (rules/, balance/, transactions/)
6. **Human-readable** - Can inspect history.tsv with any text editor
7. **Idempotent replay** - Same history.tsv → same penny.db state
8. **Audit trail** - Complete mutation history in one file

## Trade-offs

**Pros:**
- Simpler mental model (ledger = source of truth)
- Faster vault scanning (single file vs directory walk)
- Easy to version control history.tsv
- Can keep old files around without replaying them

**Cons:**
- history.tsv could become large (but still small - ~100 bytes/entry × 1000 entries = 100KB)
- Must update TWO places (history.tsv + files) on each mutation
- TSV format less robust than individual JSON manifests (one corrupted line breaks replay)

**Mitigation for corruption:**
- Regular backups of history.tsv
- Validate TSV on write (reject malformed JSON)
- Add checksum column in future if needed

## Migration Path

**Phase 1: Read-only compatibility**
- Keep existing `imports/` directory structure
- Generate history.tsv from existing entries on startup
- Use history.tsv for replay if present, else fall back to directory scan

**Phase 2: Write to both**
- New imports write to:
  1. history.tsv (append line)
  2. New file structure (rules/, balance/, transactions/)
- Old entries remain in imports/ directory

**Phase 3: Migration tool**
- `penny vault migrate` command
- Reads imports/ directory
- Writes history.tsv + new file structure
- Archives old imports/ directory

**Phase 4: Remove old code**
- Delete directory-based log code
- Remove imports/ directory from vault

## Implementation Notes

### Atomicity
When creating new entries:
```python
# 1. Write file(s) first
write_file(f"transactions/{seq}_{timestamp}/file.CSV", content)

# 2. Append to history.tsv atomically
append_line_atomic("history.tsv", f"{seq}\tingest\t{json}")

# If step 2 fails, orphaned files are harmless (ignored during replay)
# If step 1 fails, history.tsv stays consistent
```

### Concurrent Writes
- Use file locking on history.tsv for writes
- Read next sequence from last line of history.tsv
- Lock → read last seq → increment → write → unlock

### File Naming Convention
- Sequence: 4-digit zero-padded (0001, 0002, ..., 9999)
- Timestamp: ISO 8601 with colons replaced by hyphens for filesystem compatibility
  - `2024-01-15T12:00:00Z` → filename safe as-is
- Type suffix: `_rules.py`, `_balance.tsv`, or directory for transactions

## Examples

### Example 1: Import Demo Data

**history.tsv:**
```tsv
seq	mutation-type	mutation-record
0001	ingest	{"timestamp":"2024-04-05T10:00:00Z","parser":"sparkasse","csv_files":["demo.CSV"],"status":"applied","enabled":true}
0002	rules-import	{"timestamp":"2024-04-05T10:00:01Z","filename":"demo_rules.py"}
0003	balance-import	{"timestamp":"2024-04-05T10:00:02Z","filename":"balance-anchors.tsv","count":5}
```

**Files:**
```
transactions/0001_2024-04-05T10:00:00Z/
  20260404-12345678-umsatz-camt52v8.CSV
  manifest.json
rules/0002_2024-04-05T10:00:01Z_rules.py
balance/0003_2024-04-05T10:00:02Z_balance.tsv
```

### Example 2: Disable Import

**Before:**
```tsv
0003	ingest	{"timestamp":"...","enabled":true,...}
```

**After:**
```tsv
0003	ingest	{"timestamp":"...","enabled":false,...}
```

Run `penny db rebuild` - import 0003 is skipped.

### Example 3: Delete Import

**Before:**
```tsv
0001	ingest	{...}
0002	rules-import	{...}
0003	ingest	{...}
0004	balance-import	{...}
```

**After (delete seq 0003):**
```tsv
0001	ingest	{...}
0002	rules-import	{...}
0004	balance-import	{...}
```

Sequence numbers don't need to be sequential - gaps are fine.

## Future Extensions

1. **Checksums** - Add 4th column with SHA256 of file contents
2. **Multi-line records** - For very large metadata, store in separate .json file
3. **Compression** - Gzip old transaction directories
4. **Incremental replay** - Track last replayed seq in penny.db, only replay new entries

## Related ADRs

- **ADR-010**: Original vault design (now superseded)
- **ADR-008**: Classification rules (rules/ directory format)
