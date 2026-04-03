# F4U - Finance For You

Personal finance analysis app for non-technical users.

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
make server
```

### Build Distributable

```bash
# Build macOS .app and .dmg
make build
```

Output will be in `dist/`.

## Architecture

```
f4u/
├── src/f4u/
│   ├── launcher.py   # macOS menu bar app (rumps)
│   ├── server.py     # FastAPI web server
│   └── __main__.py   # Entry point
├── flake.nix         # Nix development environment
├── pyproject.toml    # Python project config + briefcase
└── Makefile          # Build commands
```

## How it Works

1. User launches F4U app
2. "F4U" appears in macOS menu bar
3. FastAPI server starts on localhost:8000
4. Browser auto-opens to dashboard
5. Menu bar provides "Open Dashboard" and "Quit F4U" options
