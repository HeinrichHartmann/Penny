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
  2. Run classification:            penny classify (or use the web UI)
  3. Review unmatched transactions  (shown in classification log)
  4. Ask your LLM to add rules:     "Add rules for these unmatched transactions: ..."
  5. Save and re-run classification
  6. Repeat until match rate is satisfactory

Tips for prompting:
  - Paste the unmatched transaction list from the classification log
  - Describe what each merchant/payee represents
  - Use hierarchical categories: "food/groceries", "transport/fuel", etc.
  - Group similar merchants in one rule for maintainability

Example prompt:
  "Add classification rules for these unmatched transactions:
   -250.00 EUR | 2024-03-15 | REWE SAGT DANKE 12345
   -45.50 EUR | 2024-03-14 | ARAL TANKSTELLE
   These are groceries and fuel respectively."

================================================================================
"""
from penny.classify import contains, is_, rule


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


# ==============================================================================
# CLASSIFICATION RULES
# ==============================================================================
# Add your rules below. Each @rule decorator specifies the category.
# Rules are evaluated in order; first match wins.

# @rule("groceries")
# def grocery_stores(tx):
#     return payee_contains(tx, "REWE", "EDEKA", "ALDI", "LIDL")

# @rule("transport/fuel")
# def gas_stations(tx):
#     return payee_contains(tx, "ARAL", "SHELL", "ESSO")

# @rule("subscriptions/streaming")
# def streaming_services(tx):
#     return payee_contains(tx, "NETFLIX", "SPOTIFY", "DISNEY")
