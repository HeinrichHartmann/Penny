from pathlib import Path

import pytest

from penny.db import init_db


def pytest_collection_modifyitems(items):
    """Mark all tests in this folder as unit tests."""
    for item in items:
        item.add_marker(pytest.mark.unit)


@pytest.fixture(autouse=True)
def configure_unit_test_storage(tmp_path, monkeypatch):
    """Run unit tests in a single process with an in-memory database."""
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PENNY_VAULT_DIR", str(tmp_path / "vault"))
    init_db(None)


@pytest.fixture
def db():
    """Fresh in-memory database for each unit test."""
    return init_db(None)


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures"
