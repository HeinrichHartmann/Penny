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

## Install the CLI

```bash
# Install the latest CLI directly from GitHub
uv tool install git+https://github.com/HeinrichHartmann/Penny.git

# Install a specific release tag
uv tool install git+https://github.com/HeinrichHartmann/Penny.git@v0.1.0
```

This installs the `penny` command as a standalone CLI tool.

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

### Publish a GitHub Release

```bash
# Authenticate GitHub CLI once
gh auth login

# Build the DMG and publish/update the GitHub Release for the current version
make release

# Validate the release inputs without publishing anything
make release-dry-run
```

`make release` publishes the `dist/Penny-<version>.dmg` artifact and a matching `.sha256`
checksum to the GitHub Release for tag `v<version>`. The current `HEAD` must already be
pushed to the branch upstream.

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
