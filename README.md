# Penny

Personal finance tracking and analysis app for non-technical users.

## Features

- Import CSV files from various bank sources
- Rule-based expense classification
- Rich reporting dashboard
- (v2) Budget tracking

## Development

### Prerequisites

- [Nix](https://nixos.org/download.html) with flakes enabled
- [direnv](https://direnv.net/) (optional but recommended)

### Setup

```bash
# Enter development environment
direnv allow
# or: nix develop

# Install dependencies
make install
```

### Run in Development

```bash
# Run full app (GUI + server)
make dev

# Run just the web server
make serve

# Open browser to dev server
make web-open
```

### Build Distributable

```bash
# Build macOS .app and .dmg
make app

# Open the built app
make app-open
```

Output will be in `dist/`.

## Architecture

```
penny/
├── src/penny/
│   ├── launcher.py   # Native Toga window
│   ├── server.py     # FastAPI web server
│   └── __main__.py   # Entry point
├── flake.nix         # Nix development environment
├── pyproject.toml    # Python project config + Briefcase
└── Makefile          # Build commands
```

## How it Works

1. User launches Penny app
2. Native Toga window appears
3. FastAPI server starts on localhost:8000
4. Browser auto-opens to dashboard
5. "Open Dashboard" button available for re-opening

## Naming

Named after Penny from The Big Bang Theory. Future views/components may follow the theme:
- **Sheldon** - Classification engine (rigid, rule-based)
- **Howard** - Import system (engineering)
- **Leonard** - Reports (sensible overview)
