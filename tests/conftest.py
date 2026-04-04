from pathlib import Path

import pytest

from penny.accounts import AccountRegistry, AccountStorage
from penny.db import init_schema, set_db_path


@pytest.fixture(autouse=True)
def reset_db_path():
    """Reset global db_path before each test to prevent state pollution."""
    set_db_path(None)
    yield
    set_db_path(None)


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
    # AccountStorage must be initialized first to create the accounts table
    # (transactions has a foreign key reference to accounts)
    AccountStorage(tmp_db)
    set_db_path(tmp_db)
    init_schema()
