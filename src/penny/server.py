"""FastAPI web server for Penny."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from penny.api import accounts_router, dashboard_router, import_router, rules_router
from penny.vault import bootstrap_application_state


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize and replay the vault-backed projection on app startup."""
    bootstrap_application_state()
    yield


app = FastAPI(title="Penny", lifespan=lifespan)

# Frontend paths
STATIC_DIR = Path(__file__).parent / "static"
FRONTEND_DIST_DIR = STATIC_DIR / "dist"
FRONTEND_INDEX_PATH = FRONTEND_DIST_DIR / "index.html"

# Mount frontend asset directories
app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets", check_dir=False), name="assets")
app.mount("/static", StaticFiles(directory=STATIC_DIR, check_dir=False), name="static")

# Mount API routers
app.include_router(accounts_router)
app.include_router(rules_router)
app.include_router(import_router)
app.include_router(dashboard_router)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page."""
    if not FRONTEND_INDEX_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend bundle is missing. Run `make frontend-build` before starting Penny.",
        )
    return HTMLResponse(content=FRONTEND_INDEX_PATH.read_text())


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the uvicorn server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
