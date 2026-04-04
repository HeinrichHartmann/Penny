from pathlib import Path

import pytest

from penny.accounts import AccountRegistry, AccountStorage
from penny.db import init_db, reset_db


@pytest.fixture(autouse=True)
def clean_db():
    """Reset database before and after each test."""
    reset_db()
    yield
    reset_db()


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def registry(tmp_db: Path) -> AccountRegistry:
    storage = AccountStorage(tmp_db)
    return AccountRegistry(storage)


@pytest.fixture
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def transaction_storage(tmp_db: Path):
    """Set up in-memory database for transaction tests."""
    # AccountStorage must be initialized first to create the accounts table
    AccountStorage(tmp_db)
    init_db(tmp_db)
