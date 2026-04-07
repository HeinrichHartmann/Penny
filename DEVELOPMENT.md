# Development

## Prerequisites

- [Nix](https://nixos.org/download.html) with flakes enabled
- [direnv](https://direnv.net/) (optional but recommended)

## Setup

```bash
# Enter development environment
direnv allow
# or: nix develop

# Install development dependencies
make dev-install

# Install pre-commit hooks
make hooks-install
```

## Run in Development

```bash
# Run full app (GUI + server)
make dev

# Run just the web server
make serve

# Install CLI locally
make install
```

## Build Distributable

```bash
# Build macOS .app and .dmg
make app

# Open the built app
make app-open
```

Output will be in `dist/`.

## Tests

The test suite is organized into:
- `tests/unit/` - single-process tests with an in-memory database
- `tests/e2e/` - CLI, API, startup, replay, and file-backed runtime tests

See [tests/testing_strategy.md](tests/testing_strategy.md) for the detailed policy.

```bash
uv run python -m pytest tests/unit -q
uv run python -m pytest tests/e2e -q
uv run python -m pytest tests -q
```

## Publish a Release

```bash
# Authenticate GitHub CLI once
gh auth login

# Build and publish to GitHub Releases
make release

# Dry run (validate without publishing)
make release-dry-run
```

`make release` publishes the `dist/Penny-<version>.dmg` artifact and a matching `.sha256` checksum to the GitHub Release for tag `v<version>`. The current `HEAD` must already be pushed upstream.
