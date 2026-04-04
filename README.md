# Penny

Penny is a local-first personal finance tool with a desktop UI for humans and a CLI for LLM-assisted collaboration.

It is built for collaborative iteration: import transactions, classify them with rules, link transfers, and inspect the result in a local dashboard.

## Current Status

Penny is pre-alpha.

Current focus:
- local desktop usage
- reproducible imports
- rule-based categorization
- transfer grouping
- iterative workflows on your own data

## Features

- Import CSV exports from supported banks
- Reconcile imports against existing accounts
- Categorize transactions with ordered Python rules
- Apply a default category to unmatched transactions
- Link transfer entries into transfer groups
- Inspect transactions, categories, and reports in the desktop UI
- Use the CLI for LLM-assisted co-creation and debugging of rules and grouping logic

## Install

### macOS Desktop App

For normal human use, install Penny from the latest DMG on GitHub Releases.

Current caveat:
- release builds are not notarized yet
- the DMG is still ad-hoc signed
- treat the desktop build as experimental for now

### CLI for LLM Collaboration

A CLI is also available for LLM-assisted workflows such as co-creating and debugging:
- classification rules
- import behavior
- transfer grouping

```bash
# Install the latest CLI directly from GitHub
uv tool install git+https://github.com/HeinrichHartmann/Penny.git

# Install a specific release tag
uv tool install git+https://github.com/HeinrichHartmann/Penny.git@v0.1.0
```

This installs the `penny` command as a standalone CLI tool.

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
