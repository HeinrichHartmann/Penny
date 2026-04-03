.PHONY: dev serve web-open app app-open build clean install sync test

# Development - run Toga GUI locally
dev: sync
	uv run python -m penny

# Run just the web server (no GUI)
serve: sync
	uv run python -m penny.server

# Open browser to dev server
web-open:
	open http://127.0.0.1:8000

# Sync dependencies
sync:
	uv sync

# Install development dependencies including briefcase
install:
	uv sync --group dev

# Build macOS app (alias for build)
app: build

# Open the built app
app-open:
	open "build/penny/macos/app/Penny.app"

# Build macOS app using briefcase
build: install
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
build-dev: install
	uv run python -m briefcase dev

# Update existing build (faster than full rebuild)
update: install
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
	@echo "  make serve     - Run just the web server (no GUI)"
	@echo "  make web-open  - Open browser to http://127.0.0.1:8000"
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
