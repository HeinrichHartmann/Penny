.PHONY: dev serve serve-api dev-web web-open web-open-dev app app-open build clean install sync test frontend-install frontend-build frontend-dev

# Development - run Toga GUI locally
dev: sync frontend-build
	uv run python -m penny

# Run frontend development server with backend proxy (default web workflow)
serve: sync frontend-install
	@backend_pid=; \
	uv run python -m penny.server & backend_pid=$$!; \
	trap 'kill $$backend_pid' EXIT INT TERM; \
	npm run dev

# Run just the API/backend server for Vite-based development
serve-api: sync
	uv run python -m penny.server

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
	open http://127.0.0.1:5173

# Sync dependencies
sync:
	uv sync

# Install development dependencies including briefcase
install: frontend-install
	uv sync --group dev

# Build macOS app (alias for build)
app: build

# Open the built app
app-open:
	open "build/penny/macos/app/Penny.app"

# Build macOS app using briefcase
build: install frontend-build
	@echo "Building macOS app..."
	yes | uv run python -m briefcase create macOS app
	uv run python -m briefcase build macOS app
	uv run python -m briefcase package macOS app --adhoc-sign
	@echo ""
	@echo "Build complete!"
	@echo "  App:  build/penny/macos/app/Penny.app"
	@echo "  DMG:  dist/"
	@ls -la dist/*.dmg 2>/dev/null || true

# Build without packaging (faster iteration)
build-dev: install frontend-build
	uv run python -m briefcase dev

# Update existing build (faster than full rebuild)
update: install frontend-build
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
test: sync
	uv run pytest tests/ -v

# Show help
help:
	@echo "Penny Development Commands:"
	@echo ""
	@echo "  make dev       - Run Toga GUI in development mode"
	@echo "  make serve     - Run Vite + backend with hot reload and open browser"
	@echo "  make serve-api - Run just the backend API server for Vite dev"
	@echo "  make dev-web   - Alias for make serve"
	@echo "  make frontend-build - Build bundled frontend assets"
	@echo "  make frontend-dev   - Run Vite dev server"
	@echo "  make web-open  - Open browser to http://127.0.0.1:8000"
	@echo "  make web-open-dev - Open browser to http://127.0.0.1:5173"
	@echo ""
	@echo "Build Commands:"
	@echo ""
	@echo "  make app       - Build macOS app (.app + .dmg)"
	@echo "  make app-open  - Open the built .app"
	@echo "  make update    - Update existing build (faster)"
	@echo "  make clean     - Remove build artifacts"
	@echo ""
	@echo "Examples:"
	@echo "  make serve web-open  - Start server and open browser"
	@echo "  make app app-open    - Rebuild and launch app"
	@echo ""
