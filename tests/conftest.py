from pathlib import Path

import pytest

from penny.db import init_db


@pytest.fixture(autouse=True)
def isolate_paths(tmp_path, monkeypatch):
    """Isolate file-backed DB and vault paths for every test."""
    monkeypatch.setenv("PENNY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("PENNY_VAULT_DIR", str(tmp_path / "vault"))


@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    return init_db(None)


@pytest.fixture(autouse=True)
def initialize_test_database(request):
    """Default all non-integration tests to a fresh in-memory DB.

    Policy:
    - Unit/domain tests talk to the DB only through penny.db and always use
      a clean in-memory database.
    - Integration tests are explicitly marked and may exercise the real
      file-backed projection via PENNY_DATA_DIR / PENNY_VAULT_DIR.
    """
    if request.node.get_closest_marker("integration"):
        return
    init_db(None)


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"
