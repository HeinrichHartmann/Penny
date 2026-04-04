"""Tests for transfer linking and consolidated queries."""

from datetime import date

import pytest

from penny.accounts import AccountRegistry, AccountStorage
from penny.db import init_schema, set_db_path
from penny.transactions import (
    Transaction,
    apply_groups,
    generate_fingerprint,
    list_transactions,
    store_transactions,
)
from penny.transfers.engine import UnionFind, link_transfers, generate_group_id


# =============================================================================
# FIXTURES
# =============================================================================


def make_transaction(
    account_id: int,
    tx_date: date,
    amount_cents: int,
    payee: str,
    *,
    subaccount_type: str = "giro",
    category: str | None = None,
    reference: str | None = None,
) -> Transaction:
    """Create a test transaction with computed fingerprint."""
    fp = generate_fingerprint(account_id, tx_date, amount_cents, payee, reference)
    return Transaction(
        fingerprint=fp,
        account_id=account_id,
        subaccount_type=subaccount_type,
        date=tx_date,
        payee=payee,
        memo="",
        amount_cents=amount_cents,
        value_date=None,
        transaction_type="",
        reference=reference,
        raw_buchungstext="",
        raw_row={},
        category=category,
    )


@pytest.fixture
def sample_transactions() -> list[Transaction]:
    """Sample transactions covering various transfer scenarios."""
    return [
        # Card settlement pair (account 1, Visa ↔ Giro, opposite amounts, 3 days apart)
        make_transaction(1, date(2024, 3, 1), 31322, "VISA CREDIT", subaccount_type="visa", category="transfer/card_settlement"),
        make_transaction(1, date(2024, 3, 4), -31322, "Visa-Abrechnung", subaccount_type="giro", category="transfer/card_settlement"),

        # Internal transfer pair (account 1 → account 2, opposite amounts, same day)
        make_transaction(1, date(2024, 3, 10), -50000, "Transfer to Shared", category="transfer/private"),
        make_transaction(2, date(2024, 3, 10), 50000, "Transfer from Private", category="transfer/shared"),

        # Tagesgeld pair (same account, Giro ↔ Tagesgeld, same day)
        make_transaction(2, date(2024, 3, 15), -100000, "Savings transfer", subaccount_type="giro", category="transfer/savings"),
        make_transaction(2, date(2024, 3, 15), 100000, "Savings transfer", subaccount_type="tagesgeld", category="transfer/savings"),

        # Standalone transfer (no matching pair)
        make_transaction(1, date(2024, 3, 20), -25000, "Outgoing transfer", category="transfer/other"),

        # Non-transfer transactions (should be ignored by link_transfers)
        make_transaction(1, date(2024, 3, 5), -1500, "Coffee shop", category="food/coffee"),
        make_transaction(2, date(2024, 3, 12), -8999, "Subscription", category="subscriptions/software"),
    ]


def sample_predicate(a: Transaction, b: Transaction) -> bool:
    """Test predicate matching the rules from ~/.local/share/penny/rules.py."""
    days_apart = abs((a.date - b.date).days)

    # Card settlements: Visa ↔ Giro, same account
    if a.category == "transfer/card_settlement" and b.category == "transfer/card_settlement":
        if a.account_id == b.account_id:
            is_visa_giro_pair = (
                (a.subaccount_type == "visa" and b.subaccount_type == "giro") or
                (a.subaccount_type == "giro" and b.subaccount_type == "visa")
            )
            if is_visa_giro_pair and a.amount_cents == -b.amount_cents and days_apart <= 5:
                return True

    # Internal transfers: different accounts
    if a.account_id != b.account_id:
        if a.amount_cents == -b.amount_cents and days_apart <= 1:
            return True

    # Tagesgeld: Giro ↔ Tagesgeld, same account, same day
    if a.account_id == b.account_id:
        is_giro_tagesgeld_pair = (
            (a.subaccount_type == "giro" and b.subaccount_type == "tagesgeld") or
            (a.subaccount_type == "tagesgeld" and b.subaccount_type == "giro")
        )
        if is_giro_tagesgeld_pair and a.amount_cents == -b.amount_cents and days_apart == 0:
            return True

    return False


# =============================================================================
# UNION-FIND TESTS
# =============================================================================


def test_union_find_basic():
    uf = UnionFind()

    # Initially each element is its own root
    assert uf.find("a") == "a"
    assert uf.find("b") == "b"

    # After union, they share the same root
    uf.union("a", "b")
    assert uf.find("a") == uf.find("b")


def test_union_find_transitive():
    uf = UnionFind()

    # a-b and b-c should result in a-b-c all connected
    uf.union("a", "b")
    uf.union("b", "c")

    assert uf.find("a") == uf.find("b") == uf.find("c")


def test_union_find_groups():
    uf = UnionFind()

    uf.union("a", "b")
    uf.union("c", "d")
    uf.find("e")  # standalone

    groups = uf.groups()

    # Should have 3 groups
    assert len(groups) == 3

    # Check group sizes
    sizes = sorted(len(members) for members in groups.values())
    assert sizes == [1, 2, 2]


# =============================================================================
# LINK_TRANSFERS TESTS
# =============================================================================


def test_link_transfers_finds_pairs(sample_transactions):
    result = link_transfers(
        sample_transactions,
        sample_predicate,
        prefix="transfer/",
        window_days=10,
    )

    # Should find 3 pairs: card settlement, internal transfer, tagesgeld
    assert result.groups_found == 3
    assert result.pairs == 3
    assert result.triplets == 0
    assert result.larger == 0


def test_link_transfers_grouped_entries_count(sample_transactions):
    result = link_transfers(
        sample_transactions,
        sample_predicate,
        prefix="transfer/",
        window_days=10,
    )

    # 6 entries grouped (3 pairs × 2), 1 standalone transfer
    assert result.grouped_entries == 6
    assert result.standalone_entries == 1  # The unmatched transfer


def test_link_transfers_ignores_non_transfers(sample_transactions):
    result = link_transfers(
        sample_transactions,
        sample_predicate,
        prefix="transfer/",
        window_days=10,
    )

    # Only 7 entries have transfer/ category
    assert result.transfer_entries == 7
    assert result.total_entries == 9


def test_link_transfers_respects_window():
    # Create entries too far apart
    entries = [
        make_transaction(1, date(2024, 1, 1), -10000, "Transfer out", category="transfer/test"),
        make_transaction(2, date(2024, 1, 20), 10000, "Transfer in", category="transfer/test"),  # 19 days apart
    ]

    def match_opposite_amounts(a, b):
        return a.amount_cents == -b.amount_cents

    result = link_transfers(entries, match_opposite_amounts, prefix="transfer/", window_days=10)

    # Should not match - outside window
    assert result.groups_found == 0


def test_link_transfers_assignments_net_to_zero(sample_transactions):
    result = link_transfers(
        sample_transactions,
        sample_predicate,
        prefix="transfer/",
        window_days=10,
    )

    # Build groups from assignments
    groups: dict[str, list[Transaction]] = {}
    tx_by_fp = {tx.fingerprint: tx for tx in sample_transactions}

    for fp, group_id in result.assignments.items():
        if group_id not in groups:
            groups[group_id] = []
        groups[group_id].append(tx_by_fp[fp])

    # Each multi-entry group should net to zero
    for group_id, members in groups.items():
        if len(members) > 1:
            net = sum(tx.amount_cents for tx in members)
            assert net == 0, f"Group {group_id} nets to {net}, expected 0"


def test_generate_group_id_deterministic():
    # Same fingerprints in any order should produce same group_id
    fps1 = ["abc", "def", "ghi"]
    fps2 = ["ghi", "abc", "def"]

    assert generate_group_id(fps1) == generate_group_id(fps2)


# =============================================================================
# STORAGE TESTS
# =============================================================================


@pytest.fixture
def storage_with_accounts(tmp_path):
    """Set up database with test accounts for foreign key constraints."""
    db_path = tmp_path / "test.db"
    account_storage = AccountStorage(db_path)
    registry = AccountRegistry(account_storage)

    # Create test accounts (IDs will be 1 and 2)
    registry.add("testbank")
    registry.add("testbank")

    # Set up transaction storage to use same database
    set_db_path(db_path)
    init_schema()


def test_group_id_never_null(storage_with_accounts):
    """group_id should be set to fingerprint for new transactions."""
    tx = make_transaction(1, date(2024, 1, 1), -1000, "Test")

    store_transactions([tx])

    stored = list_transactions(limit=1, neutralize=False)
    assert len(stored) == 1
    assert stored[0].group_id == stored[0].fingerprint


def test_consolidated_query_groups_entries(storage_with_accounts):
    """Consolidated query should collapse grouped entries."""
    # Create a pair of transactions
    tx1 = make_transaction(1, date(2024, 1, 1), -10000, "Transfer out", category="transfer/test")
    tx2 = make_transaction(2, date(2024, 1, 1), 10000, "Transfer in", category="transfer/test")

    store_transactions([tx1, tx2])

    # Apply grouping
    group_id = generate_group_id([tx1.fingerprint, tx2.fingerprint])
    apply_groups({
        tx1.fingerprint: group_id,
        tx2.fingerprint: group_id,
    })

    # Unconsolidated: 2 entries
    raw = list_transactions(neutralize=False)
    assert len(raw) == 2

    # Consolidated: 1 entry with net amount
    consolidated = list_transactions(neutralize=True)
    assert len(consolidated) == 1
    assert consolidated[0].amount_cents == 0  # -10000 + 10000
    assert consolidated[0].entry_count == 2


def test_consolidated_query_preserves_standalone(storage_with_accounts):
    """Standalone transactions should appear unchanged in consolidated view."""
    tx = make_transaction(1, date(2024, 1, 1), -5000, "Standalone")

    store_transactions([tx])

    consolidated = list_transactions(neutralize=True)
    assert len(consolidated) == 1
    assert consolidated[0].amount_cents == -5000
    assert consolidated[0].entry_count == 1
    assert consolidated[0].payee == "Standalone"


def test_apply_groups_updates_existing(storage_with_accounts):
    """apply_groups should update group_id for existing transactions."""
    tx1 = make_transaction(1, date(2024, 1, 1), -10000, "TX1")
    tx2 = make_transaction(1, date(2024, 1, 2), 10000, "TX2")

    store_transactions([tx1, tx2])

    # Initially both standalone
    raw = list_transactions(neutralize=False)
    assert all(tx.group_id == tx.fingerprint for tx in raw)

    # Apply grouping
    group_id = "test-group-123"
    grouped, standalone = apply_groups({
        tx1.fingerprint: group_id,
        tx2.fingerprint: group_id,
    })

    assert grouped == 2
    assert standalone == 0

    # Now both share group_id
    raw = list_transactions(neutralize=False)
    assert all(tx.group_id == group_id for tx in raw)
