from pathlib import Path

import pytest

from penny.db import init_default_db
from tests.helpers import FreshRuntime, build_fresh_runtime


def pytest_collection_modifyitems(items):
    """Mark all tests in this folder as end-to-end tests."""
    for item in items:
        item.add_marker(pytest.mark.e2e)


@pytest.fixture(autouse=True)
def configure_e2e_storage(request, tmp_path, monkeypatch):
    """Give each end-to-end test a fresh file-backed Penny runtime."""
    runtime = build_fresh_runtime(tmp_path, monkeypatch)
    request.node._fresh_runtime = runtime
    init_default_db()
    return runtime


@pytest.fixture
def fresh_runtime(request) -> FreshRuntime:
    """Return the fresh file-backed runtime prepared for this test."""
    return request.node._fresh_runtime


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures"
