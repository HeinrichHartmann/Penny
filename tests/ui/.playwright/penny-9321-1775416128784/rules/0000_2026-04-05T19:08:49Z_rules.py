"""Classification rules for Penny.

================================================================================
TRANSACTION SCHEMA
================================================================================

Each rule function receives a Transaction object with these attributes:

  Field                Type         Description
  ---------------------------------------------------------------------------
  payee                str          Extracted payee/merchant name
  memo                 str          Additional transaction details
  raw_buchungstext     str          Original bank description (German: "Buchungstext")
  amount_cents         int          Amount in cents (negative = expense, positive = income)
  date                 date         Transaction date
  value_date           date | None  Value/settlement date (if different from booking)
  transaction_type     str          Bank transaction type (e.g., "Ueberweisung")
  reference            str | None   Unique bank reference number
  subaccount_type      str          Account section (e.g., "giro", "savings", "depot")

  Resolved fields (read-only, for display/matching):
  ---------------------------------------------------------------------------
  account_name         str | None   User-defined display name for the account
  account_number       str | None   Bank account number (stable identifier)

================================================================================
LLM CO-CREATION GUIDE
================================================================================

This file is designed for iterative development with Claude Code or similar LLMs.

Workflow:
  1. Import your bank CSV:          penny import <file.csv>
  2. Run classification:            penny apply rules.py -v
  3. Review unmatched transactions  (shown in output)
  4. Ask your LLM to add rules:     "Add rules for these unmatched transactions: ..."
  5. Save and re-run classification
  6. Repeat until match rate is satisfactory

Tips for prompting:
  - Paste the unmatched transaction list from the classification log
  - Describe what each merchant/payee represents
  - Use hierarchical categories: "food/groceries", "transport/fuel", etc.
  - Group similar merchants in one rule for maintainability

================================================================================
"""

from penny.classify import contains, is_, rule

# =============================================================================
# DEFAULT CATEGORY
# =============================================================================
# Applied to transactions that don't match any rule.

DEFAULT_CATEGORY = "uncategorized"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def payee_is(tx, *values):
    """Match if payee exactly equals any of the given values (case-insensitive)."""
    return any(is_(tx.payee, value) for value in values)


def payee_contains(tx, *needles):
    """Match if payee contains any of the given substrings."""
    return any(contains(tx.payee, needle) for needle in needles)


def memo_contains(tx, *needles):
    """Match if memo contains any of the given substrings."""
    return any(contains(tx.memo, needle) for needle in needles)


def raw_contains(tx, *needles):
    """Match if raw bank description contains any of the given substrings."""
    return any(contains(tx.raw_buchungstext, needle) for needle in needles)


def text_contains(tx, *needles):
    """Match if any text field contains the given substrings."""
    return payee_contains(tx, *needles) or memo_contains(tx, *needles) or raw_contains(tx, *needles)


# =============================================================================
# INCOME
# =============================================================================


@rule("income/salary")
def salary(tx):
    """Monthly salary deposits."""
    if tx.amount_cents <= 0:
        return False
    return payee_contains(tx, "Employer", "GmbH") and memo_contains(tx, "Gehalt", "Lohn")


# =============================================================================
# HOUSING & UTILITIES
# =============================================================================


@rule("housing/rent")
def rent(tx):
    """Monthly rent payments."""
    return payee_contains(tx, "Hausverwaltung") or memo_contains(tx, "Miete")


@rule("utilities/electricity")
def electricity(tx):
    """Electricity bills."""
    return payee_contains(tx, "Stadtwerke") or memo_contains(tx, "Strom")


@rule("utilities/internet")
def internet(tx):
    """Internet and phone bills."""
    return payee_contains(tx, "Telekom", "Vodafone", "O2") or memo_contains(tx, "DSL", "Telefon")


@rule("utilities/insurance")
def insurance(tx):
    """Insurance premiums."""
    return payee_contains(tx, "Versicherung") or memo_contains(tx, "Versicherung")


# =============================================================================
# FOOD & DINING
# =============================================================================


@rule("food/groceries")
def groceries(tx):
    """Supermarket and grocery stores."""
    return payee_contains(tx, "REWE", "EDEKA", "ALDI", "LIDL", "Kaufland", "Netto", "Penny")


@rule("food/drugstore")
def drugstore(tx):
    """Drugstores and personal care."""
    return payee_contains(tx, "DM-Drogerie", "DM ", "ROSSMANN", "Mueller")


@rule("food/restaurant")
def restaurants(tx):
    """Restaurants and dining out."""
    return payee_contains(
        tx,
        "Restaurant",
        "Cafe",
        "Café",
        "Pizzeria",
        "Burger King",
        "McDonald",
        "Asia Wok",
        "Bistro",
        "Kebab",
        "Sushi",
    )


@rule("food/bakery")
def bakery(tx):
    """Bakeries and coffee shops."""
    return payee_contains(tx, "Bäckerei", "Baeckerei", "Backerei", "Starbucks")


# =============================================================================
# TRANSPORT
# =============================================================================


@rule("transport/fuel")
def fuel(tx):
    """Gas stations."""
    return payee_contains(tx, "Tankstelle", "ARAL", "SHELL", "ESSO", "JET ", "Total")


@rule("transport/public")
def public_transport(tx):
    """Public transportation."""
    return payee_contains(tx, "Deutsche Bahn", "DB ", "BVG", "MVG", "VBB")


# =============================================================================
# SHOPPING
# =============================================================================


@rule("shopping/amazon")
def amazon(tx):
    """Amazon purchases."""
    return payee_contains(tx, "AMAZON", "AMZN")


@rule("shopping/online")
def online_shopping(tx):
    """General online shopping."""
    return payee_contains(tx, "PAYPAL", "KLARNA", "Zalando", "Otto", "MediaMarkt")


# =============================================================================
# SUBSCRIPTIONS
# =============================================================================


@rule("subscriptions/streaming")
def streaming(tx):
    """Streaming services."""
    return payee_contains(tx, "NETFLIX", "SPOTIFY", "DISNEY", "Prime Video", "YouTube")


@rule("subscriptions/software")
def software(tx):
    """Software subscriptions."""
    return payee_contains(tx, "APPLE.COM", "GITHUB", "Microsoft", "Adobe", "Google")


# =============================================================================
# CASH & BANKING
# =============================================================================


@rule("cash/atm")
def atm_withdrawal(tx):
    """ATM cash withdrawals."""
    return memo_contains(tx, "Bargeldauszahlung", "Geldautomat", "ATM")


@rule("banking/fees")
def bank_fees(tx):
    """Bank fees and charges."""
    return memo_contains(tx, "Entgelt", "Gebühr", "Kontoführung")


# =============================================================================
# TRANSFERS (for grouping)
# =============================================================================


@rule("transfer/internal")
def internal_transfer(tx):
    """Transfers between own accounts."""
    return memo_contains(tx, "Umbuchung", "Übertrag")


# =============================================================================
# TRANSFER GROUPING
# =============================================================================
# Link related transfer entries (e.g., money moved between your own accounts).

TRANSFER_PREFIX = "transfer/"
TRANSFER_WINDOW_DAYS = 10


def in_same_transfer_group(a, b):
    """Group matching transfers between accounts.

    Called for pairs of entries that both have category starting with
    TRANSFER_PREFIX and are within TRANSFER_WINDOW_DAYS of each other.
    """
    # Different accounts
    if a.account_id == b.account_id:
        return False
    # Opposite amounts
    if a.amount_cents != -b.amount_cents:
        return False
    # Within a few days
    days_apart = abs((a.date - b.date).days)
    return days_apart <= 3
