"""Business logic for account management."""

from penny.accounts.models import Account, Subaccount
from penny.accounts.storage import AccountStorage
from penny.import_.base import DetectionResult


class DuplicateAccountError(ValueError):
    """Raised when an account already exists."""


class AccountRegistry:
    """High-level account operations."""

    def __init__(self, storage: AccountStorage):
        self.storage = storage

    def add(self, bank: str, bank_account_number: str | None = None, **kwargs) -> Account:
        """Create a new account."""

        if bank_account_number:
            existing = self.storage.find_account_by_bank_account_number(
                bank,
                bank_account_number,
                include_hidden=True,
            )
            if existing is not None:
                raise DuplicateAccountError(
                    f"Account already exists for {bank} account number {bank_account_number}"
                )

        bank_account_numbers = [bank_account_number] if bank_account_number else []
        return self.storage.create_account(
            bank=bank,
            bank_account_numbers=bank_account_numbers,
            **kwargs,
        )

    def remove(self, account_id: int) -> bool:
        """Soft-delete an account."""

        return self.storage.soft_delete_account(account_id)

    def list(self, include_hidden: bool = False) -> list[Account]:
        """List accounts."""

        return self.storage.list_accounts(include_hidden=include_hidden)

    def get(self, account_id: int) -> Account | None:
        """Get an account by ID, including hidden entries."""

        return self.storage.get_account(account_id, include_hidden=True)

    def find_by_bank_account_number(self, bank: str, account_number: str) -> Account | None:
        """Find an account by bank and bank account number."""

        return self.storage.find_account_by_bank_account_number(
            bank,
            account_number,
            include_hidden=False,
        )

    def reconcile(self, detection: DetectionResult) -> Account:
        """Find or create the account for a detected CSV file."""

        if not detection.bank_account_number:
            raise ValueError("Cannot reconcile account without a bank account number")

        account = self.find_by_bank_account_number(detection.bank, detection.bank_account_number)
        if account is not None:
            self.storage.upsert_subaccounts(account.id, detection.detected_subaccounts)
            refreshed = self.get(account.id)
            return refreshed if refreshed is not None else account

        subaccounts = {
            subaccount_type: Subaccount(type=subaccount_type)
            for subaccount_type in detection.detected_subaccounts
        }
        return self.add(
            detection.bank,
            bank_account_number=detection.bank_account_number,
            subaccounts=subaccounts,
        )
