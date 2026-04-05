.PHONY: dev serve serve-api serve-fresh dev-web web-open web-open-dev app app-open build release release-dry-run clean install dev-install sync test lint lint-fix format frontend-install frontend-build frontend-dev

# Development - run Toga GUI locally
dev: sync frontend-build
	uv run python -m penny

# Run frontend development server with backend proxy (default web workflow)
serve: sync frontend-install
	@backend_pid=; \
	uv run python -c "from penny.server import run_server; run_server(port=8001)" & backend_pid=$$!; \
	trap 'kill $$backend_pid' EXIT INT TERM; \
	npm run dev

# Run just the API/backend server for Vite-based development
serve-api: sync
	uv run python -c "from penny.server import run_server; run_server(port=8001)"

# Run server with clean database in /tmp/Penny-$port
serve-fresh: sync frontend-build
	@PORT=$$((8000 + RANDOM % 4000)); \
	VAULT_DIR="/tmp/Penny-$$PORT"; \
	URL="http://127.0.0.1:$$PORT"; \
	echo "Starting fresh Penny instance:"; \
	echo "  Port:      $$PORT"; \
	echo "  Vault dir: $$VAULT_DIR"; \
	echo "  URL:       $$URL"; \
	echo ""; \
	trap 'echo ""; echo "Cleaning up $$VAULT_DIR..."; rm -rf "$$VAULT_DIR"' EXIT INT TERM; \
	(sleep 1 && echo "Opening browser..." && open "$$URL") & \
	PENNY_VAULT_DIR="$$VAULT_DIR" uv run python -c "from penny.server import run_server; run_server(port=$$PORT)"

# Install frontend dependencies locally
frontend-install:
	npm ci

# Build frontend assets with Vite
frontend-build: frontend-install
	npm run build

# Run Vite dev server directly
frontend-dev: frontend-install
	npm run dev

# Run backend + Vite dev server with HMR (no frontend build)
dev-web: serve

# Open browser to dev server
web-open:
	open http://127.0.0.1:8000

# Open browser to Vite dev server
web-open-dev:
	open http://127.0.0.1:8000

# Sync dependencies
sync:
	uv sync

# Install the standalone Penny CLI tool from this checkout
install:
	uv tool install --reinstall --force .

# Install development dependencies including briefcase
dev-install: frontend-install
	uv sync --group dev

# Build macOS app (alias for build)
app: build

# Open the built app
app-open:
	open "build/penny/macos/app/Penny.app"

# Build macOS app using briefcase
build: dev-install frontend-build
	@echo "Building macOS app..."
	yes | uv run python -m briefcase create macOS app
	uv run python -m briefcase build macOS app
	uv run python -m briefcase package macOS app --adhoc-sign
	@echo ""
	@echo "Build complete!"
	@echo "  App:  build/penny/macos/app/Penny.app"
	@echo "  DMG:  dist/"
	@ls -la dist/*.dmg 2>/dev/null || true

# Build and publish a GitHub release for the current version
release: build
	./scripts/release.sh

# Validate the release inputs without creating or updating a GitHub release
release-dry-run: build
	DRY_RUN=1 ./scripts/release.sh

# Build without packaging (faster iteration)
build-dev: dev-install frontend-build
	uv run python -m briefcase dev

# Update existing build (faster than full rebuild)
update: dev-install frontend-build
	uv run python -m briefcase update macOS app
	uv run python -m briefcase build macOS app

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf .briefcase/
	rm -rf __pycache__ src/penny/__pycache__
	rm -rf *.egg-info
	@echo "Cleaned build artifacts"

# Run tests
test: dev-install
	uv run python -m pytest tests/ -v

# Lint code (check only)
lint: dev-install
	uv run ruff check src/penny tests
	uv run ruff format --check src/penny tests

# Lint and fix auto-fixable issues
lint-fix: dev-install
	uv run ruff check --fix src/penny tests
	uv run ruff format src/penny tests

# Format code
format: dev-install
	uv run ruff format src/penny tests

# Show help
help:
	@echo "Penny Development Commands:"
	@echo ""
	@echo "  make dev       - Run Toga GUI in development mode"
	@echo "  make serve     - Run Vite + backend with hot reload and open browser"
	@echo "  make serve-api - Run just the backend API server on http://127.0.0.1:8001"
	@echo "  make serve-fresh - Run server with clean database on random port (8000-12000)"
	@echo "  make dev-web   - Alias for make serve"
	@echo "  make install   - Install the standalone penny CLI tool from this checkout"
	@echo "  make dev-install - Install development dependencies for working on the repo"
	@echo "  make frontend-build - Build bundled frontend assets"
	@echo "  make frontend-dev   - Run Vite dev server on http://127.0.0.1:8000"
	@echo "  make web-open  - Open browser to http://127.0.0.1:8000"
	@echo "  make web-open-dev - Open browser to http://127.0.0.1:8000"
	@echo ""
	@echo "Build Commands:"
	@echo ""
	@echo "  make app       - Build macOS app (.app + .dmg)"
	@echo "  make release   - Build and publish the current version to GitHub Releases"
	@echo "  make release-dry-run - Validate the release command without publishing"
	@echo "  make app-open  - Open the built .app"
	@echo "  make update    - Update existing build (faster)"
	@echo "  make test      - Run the test suite"
	@echo "  make clean     - Remove build artifacts"
	@echo ""
	@echo "Examples:"
	@echo "  make serve web-open  - Start server and open browser"
	@echo "  make app app-open    - Rebuild and launch app"
	@echo ""
