"""API routers for Penny."""

from penny.api.accounts import router as accounts_router
from penny.api.dashboard import router as dashboard_router
from penny.api.import_ import router as import_router
from penny.api.rules import router as rules_router

__all__ = [
    "accounts_router",
    "dashboard_router",
    "import_router",
    "rules_router",
]
