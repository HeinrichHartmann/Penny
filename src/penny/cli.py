"""Penny CLI."""

from __future__ import annotations

from pathlib import Path
from collections import Counter

import click

from penny.accounts import AccountRegistry, AccountStorage, DuplicateAccountError
from penny.classify import load_rules
from penny.classify.engine import _load_module, _ACTIVE_COLLECTOR, RuleCollector
from penny.ingest import (
    DetectionError,
    get_supported_csv_types,
    match_file,
    read_file_with_encoding,
)
from penny.transactions import TransactionStorage
from penny.transfers import link_transfers


def get_registry() -> AccountRegistry:
    """Construct the default account registry."""

    return AccountRegistry(AccountStorage())


def get_transaction_storage() -> TransactionStorage:
    """Construct the default transaction storage."""

    return TransactionStorage()


def _format_account_row(account) -> str:
    name = account.display_name or "-"
    iban = account.iban or "-"
    status = "hidden" if account.hidden else "active"
    return f"{account.id:<3} {account.bank:<12} {name:<20} {iban:<24} {status}"


@click.group()
def main():
    """Penny - Personal finance manager."""


@main.group()
def accounts():
    """Manage bank accounts."""


@accounts.command("add")
@click.argument("bank")
@click.option("--account-number", "-n", help="Bank account number")
@click.option("--display-name", "-d", help="Display name")
@click.option("--iban", help="IBAN")
def accounts_add(bank: str, account_number: str | None, display_name: str | None, iban: str | None):
    """Add a new bank account."""

    registry = get_registry()
    try:
        account = registry.add(
            bank,
            bank_account_number=account_number,
            display_name=display_name,
            iban=iban,
        )
    except DuplicateAccountError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Created account #{account.id}: {account.bank}")


@accounts.command("remove")
@click.argument("account_id", type=int)
def accounts_remove(account_id: int):
    """Remove an account by hiding it."""

    registry = get_registry()
    if not registry.remove(account_id):
        raise click.ClickException(f"Account #{account_id} not found")

    click.echo(f"Removed account #{account_id}")


@accounts.command("list")
@click.option("--all", "include_hidden", is_flag=True, help="Include hidden accounts")
def accounts_list(include_hidden: bool):
    """List all accounts."""

    registry = get_registry()
    account_list = registry.list(include_hidden=include_hidden)
    if not account_list:
        click.echo("No accounts found.")
        return

    click.echo("ID  Bank         Name                 IBAN                     Status")
    for account in account_list:
        click.echo(_format_account_row(account))


@main.group()
def transactions():
    """View transactions."""


SUPPORTED_CSV_TYPES = get_supported_csv_types()


@main.command("import")
@click.argument("csv_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--csv-type",
    type=click.Choice(SUPPORTED_CSV_TYPES, case_sensitive=False),
    help=f"Explicit parser selection. Supported types: {', '.join(SUPPORTED_CSV_TYPES)}",
)
@click.option("--dry-run", is_flag=True, help="Parse but do not persist accounts or transactions")
def import_csv(csv_file: Path, csv_type: str | None, dry_run: bool):
    """Import transactions from a CSV file."""

    content = read_file_with_encoding(csv_file)

    try:
        parser = match_file(csv_file.name, content, csv_type=csv_type)
    except DetectionError as exc:
        raise click.ClickException(str(exc)) from exc

    registry = get_registry()
    detection = parser.detect(csv_file.name, content)
    existing_account = registry.find_by_bank_account_number(detection.bank, detection.bank_account_number)

    if dry_run:
        account_id = existing_account.id if existing_account is not None else 0
        account_label = (
            f"#{existing_account.id} ({existing_account.bank} {detection.bank_account_number})"
            if existing_account is not None
            else f"[new] ({detection.bank} {detection.bank_account_number})"
        )
    else:
        try:
            account = registry.reconcile(detection)
        except (DuplicateAccountError, ValueError) as exc:
            raise click.ClickException(str(exc)) from exc
        account_id = account.id
        account_label = f"#{account.id} ({account.bank} {detection.bank_account_number})"

    parsed_transactions = parser.parse(csv_file.name, content, account_id=account_id)
    section_counts = Counter(transaction.subaccount_type for transaction in parsed_transactions)
    sections_text = ", ".join(
        f"{section} ({count})" for section, count in sorted(section_counts.items())
    ) or "-"

    click.echo(f"Detected: {detection.parser_name}")
    click.echo(f"Account: {account_label}")
    click.echo(f"Sections: {sections_text}")

    if dry_run:
        click.echo(f"Parsed: {len(parsed_transactions)} transactions")
        for transaction in parsed_transactions[:5]:
            click.echo(
                f"  {transaction.date.isoformat()} | "
                f"{transaction.payee[:30]:<30} | {transaction.amount_cents / 100:>8.2f}"
            )
        return

    storage = get_transaction_storage()
    new_count, duplicate_count = storage.store_transactions(
        parsed_transactions,
        source_file=csv_file.name,
    )

    click.echo("")
    click.echo("Importing...")
    click.echo(f"  New: {new_count} transactions")
    click.echo(f"  Duplicates: {duplicate_count} (skipped)")
    click.echo("")
    click.echo("Done.")


@transactions.command("list")
@click.option("--account", "-a", "account_id", type=int, help="Filter by account ID")
@click.option("--limit", "-n", default=20, show_default=True, help="Number of transactions")
def transactions_list(account_id: int | None, limit: int):
    """List recent transactions."""

    storage = get_transaction_storage()
    transaction_list = storage.list_transactions(account_id=account_id, limit=limit)
    if not transaction_list:
        click.echo("No transactions found.")
        return

    for transaction in transaction_list:
        click.echo(
            f"{transaction.date.isoformat()} | "
            f"{transaction.payee[:25]:<25} | {transaction.amount_cents / 100:>10.2f} | "
            f"{transaction.category or '-'}"
        )


@main.command("classify")
@click.argument("rules_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def classify(rules_file: Path):
    """Classify all imported transactions using a Python rules module."""

    storage = get_transaction_storage()
    transactions = storage.list_transactions(limit=None)
    if not transactions:
        click.echo("No transactions found.")
        return

    ruleset = load_rules(rules_file)
    decisions = []
    category_counts: Counter[str] = Counter()

    for transaction in transactions:
        decision = ruleset.classify(transaction)
        if decision is None:
            continue
        decisions.append(decision)
        category_counts[decision.category] += 1

    matched_count, unmatched_count = storage.apply_classifications(decisions)

    click.echo(f"Loaded rules: {rules_file}")
    click.echo(f"Rules: {len(ruleset.rules)}")
    click.echo(f"Matched: {matched_count}")
    click.echo(f"Unmatched: {unmatched_count}")
    for category, count in sorted(category_counts.items()):
        click.echo(f"  {category}: {count}")


@main.command("link-transfers")
@click.argument("rules_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Show what would be linked without persisting")
def link_transfers_cmd(rules_file: Path, dry_run: bool):
    """Link transfer entries into groups using rules from a Python module.

    The rules file should define:

    \b
      TRANSFER_PREFIX = "transfer/"      # Category prefix to filter
      TRANSFER_WINDOW_DAYS = 10          # Max days apart for comparison
      def in_same_transfer_group(a, b):  # Predicate function
          return ...
    """
    # Load the rules module (with context for @rule decorators)
    collector = RuleCollector(rules_file)
    token = _ACTIVE_COLLECTOR.set(collector)
    try:
        module = _load_module(rules_file)
    finally:
        _ACTIVE_COLLECTOR.reset(token)

    # Extract transfer config
    prefix = getattr(module, "TRANSFER_PREFIX", "transfer/")
    window_days = getattr(module, "TRANSFER_WINDOW_DAYS", 10)
    predicate = getattr(module, "in_same_transfer_group", None)

    if predicate is None:
        raise click.ClickException(
            f"Rules file must define 'in_same_transfer_group(a, b)' function"
        )

    click.echo(f"Loaded rules: {rules_file}")
    click.echo(f"  TRANSFER_PREFIX = {prefix!r}")
    click.echo(f"  TRANSFER_WINDOW_DAYS = {window_days}")
    click.echo("")

    # Load all transactions (unconsolidated - need raw entries for linking)
    storage = get_transaction_storage()
    entries = storage.list_transactions(limit=None, consolidated=False)
    if not entries:
        click.echo("No entries found.")
        return

    # Run linking
    result = link_transfers(entries, predicate, prefix=prefix, window_days=window_days)

    click.echo(f"Entries: {result.total_entries} total, {result.transfer_entries} transfers")
    click.echo(f"Groups found: {result.groups_found}")
    click.echo(f"  - {result.pairs} pairs (2 entries)")
    click.echo(f"  - {result.triplets} triplets (3 entries)")
    click.echo(f"  - {result.larger} larger groups (max {result.max_group_size} entries)")
    click.echo("")

    if dry_run:
        click.echo(f"Dry run: would link {result.grouped_entries} entries into {result.groups_found} groups")
        return

    # Apply to database
    grouped, standalone = storage.apply_groups(result.assignments)
    click.echo(f"Linked: {grouped} entries into groups")
    click.echo(f"Standalone: {standalone} entries")
    click.echo("")
    click.echo("Done.")


if __name__ == "__main__":
    main()
