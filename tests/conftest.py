from pathlib import Path

import pytest

from penny.db import init_db


@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    return init_db(None)


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"
