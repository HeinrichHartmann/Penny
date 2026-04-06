"""Demo classification rules for Penny sample data."""

from penny.classify import contains, rule

# ── Income ────────────────────────────────────────────────────────────────────


@rule("Income:Salary")
def salary(tx):
    return contains(tx.payee, "Demo Employer") and tx.amount_cents > 0


# ── Housing ───────────────────────────────────────────────────────────────────


@rule("Housing:Rent")
def rent(tx):
    return contains(tx.payee, "Hausverwaltung") and tx.amount_cents < 0


# ── Utilities ─────────────────────────────────────────────────────────────────


@rule("Utilities:Phone")
def phone(tx):
    return contains(tx.payee, "Telekom") and tx.amount_cents < 0


@rule("Utilities:Power")
def power(tx):
    return contains(tx.payee, "Stadtwerke") and tx.amount_cents < 0


# ── Insurance ─────────────────────────────────────────────────────────────────


@rule("Insurance:General")
def insurance(tx):
    return contains(tx.payee, "Versicherung") and tx.amount_cents < 0


# ── Groceries ─────────────────────────────────────────────────────────────────


@rule("Groceries:Supermarket")
def supermarket(tx):
    payee_lower = tx.payee.lower()
    return (
        any(store in payee_lower for store in ["rewe", "edeka", "lidl", "aldi", "kaufland"])
        and tx.amount_cents < 0
    )


@rule("Groceries:Drugstore")
def drugstore(tx):
    payee_lower = tx.payee.lower()
    return any(store in payee_lower for store in ["dm", "rossmann"]) and tx.amount_cents < 0


# ── Shopping ──────────────────────────────────────────────────────────────────


@rule("Shopping:Online")
def online_shopping(tx):
    payee_lower = tx.payee.lower()
    return any(store in payee_lower for store in ["amazon", "otto"]) and tx.amount_cents < 0


# ── Transportation ────────────────────────────────────────────────────────────


@rule("Transportation:Fuel")
def fuel(tx):
    return contains(tx.payee, "Total") and tx.amount_cents < 0


# ── Entertainment ─────────────────────────────────────────────────────────────


@rule("Entertainment:Streaming")
def streaming(tx):
    payee_lower = tx.payee.lower()
    return any(service in payee_lower for service in ["spotify", "netflix"]) and tx.amount_cents < 0


# ── Health & Fitness ──────────────────────────────────────────────────────────


@rule("Health:Fitness")
def fitness(tx):
    return contains(tx.payee, "Fitness") and tx.amount_cents < 0


# ── Cash & ATM ────────────────────────────────────────────────────────────────


@rule("Cash:ATM")
def atm(tx):
    return contains(tx.payee, "Geldautomat") and tx.amount_cents < 0


# ── Transfers ─────────────────────────────────────────────────────────────────


@rule("Transfer:Internal")
def internal_transfer(tx):
    return contains(tx.payee, "Eigene Überweisung")
