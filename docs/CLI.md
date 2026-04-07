# CLI Reference

The CLI shares state with the desktop app and enables LLM-assisted workflows.

## Install

```bash
uv tool install git+https://github.com/HeinrichHartmann/Penny.git
```

## Import & Archive

```bash
# Import a bank CSV (parser auto-detected or explicit)
penny import ~/Downloads/umsaetze.csv
penny import ~/Downloads/export.csv --csv-type sparkasse

# Apply classification rules
penny apply rules.py -v

# Import rules into the vault
penny import-rules rules.py
```

## Viewing Data

```bash
# List accounts
penny accounts list

# List recent transactions
penny transactions list --limit 20
penny transactions list --from 2024-01-01 --to 2024-03-31
penny transactions list --category "food" --account 1
penny transactions list -q "REWE"

# Pivot table by category
penny pivot --from 2024-01-01 --to 2024-12-31 -d 2
penny pivot --tab income
```

## Reports

```bash
# Comprehensive financial report
penny report 2024              # Full year
penny report 2024-03           # Single month
penny report 2024 -a Shared    # Filter by account
```

## Vault & Database

```bash
# Check vault status
penny vault status

# Rebuild database from archived imports
penny db rebuild

# View import history
penny log list
```

## Server

```bash
# Start the web server (used by desktop app)
penny serve
```
