from pathlib import Path

import pytest

from penny.accounts import AccountRegistry, AccountStorage
from penny.transactions import TransactionStorage


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
def transaction_storage(tmp_db: Path) -> TransactionStorage:
    # AccountStorage must be initialized first to create the accounts table
    # (transactions has a foreign key reference to accounts)
    AccountStorage(tmp_db)
    return TransactionStorage(tmp_db)
