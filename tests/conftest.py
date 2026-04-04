from pathlib import Path

import pytest

from penny.accounts import AccountRegistry, AccountStorage
from penny.db import init_db


@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    return init_db(None)


@pytest.fixture
def registry(db) -> AccountRegistry:
    """Account registry using in-memory database."""
    return AccountRegistry(AccountStorage())


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"
