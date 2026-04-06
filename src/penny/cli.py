"""Penny CLI."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

import click

from penny.accounts import (
    DuplicateAccountError,
    add_account,
    find_account_by_bank_account_number,
    list_accounts,
    remove_account,
)
from penny.classify import run_classification_pass
from penny.classify.engine import _ACTIVE_COLLECTOR, LoadedRulesConfig, RuleCollector, _load_module
from penny.db import init_db, init_default_db
from penny.ingest import (
    DetectionError,
    get_supported_csv_types,
    match_file,
    read_file_with_encoding,
)
from penny.reports import generate_report_text
from penny.runtime_rules import run_stored_rules
from penny.server import run_server
from penny.transactions import (
    TransactionFilter,
    apply_classifications,
    apply_groups,
    list_transactions,
)
from penny.transfers import link_transfers
from penny.vault import (
    IngestRequest,
    VaultConfig,
    ensure_vault_initialized,
    latest_rules_path,
    replay_vault,
    save_rules_snapshot,
)
from penny.vault import (
    ingest_csv as ingest_vault_csv,
)
from penny.vault.ledger import Ledger


def _load_rules_bundle(rules_file: Path) -> tuple[LoadedRulesConfig, object]:
    """Load rules once and return both config and raw module."""
    collector = RuleCollector(rules_file)
    token = _ACTIVE_COLLECTOR.set(collector)
    try:
        module = _load_module(rules_file)
        config = LoadedRulesConfig(
            ruleset=collector.build(),
            default_category=getattr(module, "DEFAULT_CATEGORY", "uncategorized"),
        )
        return config, module
    finally:
        _ACTIVE_COLLECTOR.reset(token)


def _extract_transfer_settings(module: object) -> tuple[str, int, object | None]:
    """Read optional transfer-linking hooks from the rules module."""
    return (
        getattr(module, "TRANSFER_PREFIX", "transfer/"),
        getattr(module, "TRANSFER_WINDOW_DAYS", 10),
        getattr(module, "in_same_transfer_group", None),
    )


def _format_account_row(account) -> str:
    name = account.display_name or "-"
    iban = account.iban or "-"
    status = "hidden" if account.hidden else "active"
    return f"{account.id:<3} {account.bank:<12} {name:<20} {iban:<24} {status}"


def _build_transaction_filter(
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    account_ids: tuple[int, ...] = (),
    category: str | None = None,
    query: str | None = None,
    tab: str | None = None,
) -> TransactionFilter:
    return TransactionFilter(
        from_date=from_date.date() if from_date else None,
        to_date=to_date.date() if to_date else None,
        account_ids=frozenset(account_ids) if account_ids else None,
        category_prefix=category,
        search_query=query,
        tab=tab,
    )


def _echo_classification_lines(transactions, decisions, traces, *, verbose: int) -> None:
    """Print verbose classification output."""
    if verbose <= 0:
        return

    decisions_by_fingerprint = {decision.fingerprint: decision for decision in decisions}

    for transaction in transactions:
        decision = decisions_by_fingerprint.get(transaction.fingerprint)
        if decision is None:
            continue

        if verbose == 1:
            click.echo(
                f"{transaction.date.isoformat()} | "
                f"{transaction.payee[:30]:<30} | "
                f"{transaction.amount_cents / 100:>9.2f} | "
                f"{decision.category} | "
                f"rule={decision.rule_name}"
            )
            continue

        click.echo(
            f"{transaction.date.isoformat()} | "
            f"{transaction.payee[:30]:<30} | "
            f"{transaction.amount_cents / 100:>9.2f}"
        )
        for evaluation in traces.get(transaction.fingerprint, []):
            status = "yes" if evaluation.matched else "no"
            suffix = f" !! {evaluation.error}" if evaluation.error else ""
            click.echo(f"  [{status}] {evaluation.rule_name} -> {evaluation.category}{suffix}")
        click.echo(f"  => {decision.rule_name} -> {decision.category}")


def _echo_classification_summary(rules_file: Path, config: LoadedRulesConfig, result) -> None:
    """Print the compact classification summary."""
    click.echo(f"Loaded rules: {rules_file}")
    click.echo(f"Rules: {len(config.ruleset.rules)}")
    click.echo(f"Default category: {config.default_category}")
    click.echo(f"Matched: {result.matched_count}")
    click.echo(f"Default: {result.default_count}")
    for category, count in sorted(result.category_counts.items()):
        click.echo(f"  {category}: {count}")


def _apply_rules(rules_file: Path, *, verbose: int = 0) -> None:
    """Apply classification rules and optional transfer linking."""
    transactions = list_transactions(limit=None, neutralize=False, include_hidden=True)
    if not transactions:
        click.echo("No transactions found.")
        return

    config, module = _load_rules_bundle(rules_file)
    result = run_classification_pass(
        transactions,
        config,
        collect_rule_trace=verbose >= 2,
    )

    if result.errors:
        for error in result.errors:
            click.echo(f"Error classifying {error.payee}: {error.error}", err=True)
        raise click.ClickException(f"{len(result.errors)} classification errors")

    apply_classifications(result.decisions)
    _echo_classification_lines(
        transactions,
        result.decisions,
        result.traces,
        verbose=verbose,
    )
    _echo_classification_summary(rules_file, config, result)

    decisions_by_fingerprint = {decision.fingerprint: decision for decision in result.decisions}
    for transaction in transactions:
        decision = decisions_by_fingerprint[transaction.fingerprint]
        transaction.category = decision.category
        transaction.classification_rule = decision.rule_name

    prefix, window_days, predicate = _extract_transfer_settings(module)
    if predicate is None:
        click.echo("")
        click.echo("Transfer linking: skipped (no in_same_transfer_group defined)")
        return

    transfer_result = link_transfers(
        transactions,
        predicate,
        prefix=prefix,
        window_days=window_days,
    )
    apply_groups(transfer_result.assignments)

    click.echo("")
    click.echo("Transfers:")
    click.echo(f"  Prefix: {prefix!r}")
    click.echo(f"  Window: {window_days} days")
    click.echo(f"  Groups found: {transfer_result.groups_found}")
    click.echo(f"  Linked entries: {transfer_result.grouped_entries}")
    click.echo(f"  Standalone transfers: {transfer_result.standalone_entries}")


@click.group()
def main():
    """Penny - Personal finance manager."""
    init_default_db()


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

    try:
        account = add_account(
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

    if not remove_account(account_id):
        raise click.ClickException(f"Account #{account_id} not found")

    click.echo(f"Removed account #{account_id}")


@accounts.command("list")
@click.option("--all", "include_hidden", is_flag=True, help="Include hidden accounts")
def accounts_list(include_hidden: bool):
    """List all accounts."""

    account_list = list_accounts(include_hidden=include_hidden)
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


@main.group()
def vault():
    """Manage the portable vault and SQLite projection."""


@main.group()
def db():
    """Manage the SQLite projection database."""


@main.group()
def log():
    """Inspect archived ingest log entries."""


@vault.command("init")
def vault_init():
    """Initialize the portable Penny directory."""
    config = VaultConfig()
    created = ensure_vault_initialized(config)
    ledger = Ledger(config.path)

    click.echo(f"Vault: {config.path}")
    if created:
        click.echo("Status: initialized")
        click.echo("Imports: 0")
        click.echo("Rules snapshots: 0")
        click.echo("Mutations: 0")
    else:
        entries = ledger.read_entries()
        ingest_count = sum(1 for e in entries if e.entry_type == "ingest")
        click.echo("Status: already initialized")
        click.echo(f"Imports: {ingest_count}")


@vault.command("status")
def vault_status():
    """Show vault and projection status."""
    config = VaultConfig()
    ledger = Ledger(config.path)
    latest_rules = latest_rules_path(config)

    click.echo(f"Vault: {config.path}")
    click.echo(f"Projection DB: {config.db_path}")
    click.echo(f"Initialized: {'yes' if config.is_initialized() else 'no'}")

    if not config.is_initialized():
        click.echo("Ledger entries: 0")
        click.echo("Rules snapshots: 0")
        return

    # Count entries in ledger by type
    entries = ledger.read_entries()
    ingest_count = sum(1 for e in entries if e.entry_type == "ingest")
    mutation_count = sum(1 for e in entries if e.entry_type == "mutation")
    balance_count = sum(1 for e in entries if e.entry_type == "balance")
    click.echo(f"Imports: {ingest_count}")
    click.echo(f"Mutations: {mutation_count}")
    click.echo(f"Balance snapshots: {balance_count}")
    click.echo(f"Rules snapshots: {len(list(config.rules_dir.glob('*_rules.py')))}")
    if latest_rules is not None:
        click.echo(f"Latest rules: {latest_rules.name}")


@vault.command("replay")
def vault_replay():
    """Rebuild the SQLite projection from archived imports."""
    config = VaultConfig()
    created = ensure_vault_initialized(config)
    result = replay_vault(config)

    click.echo(f"Vault: {config.path}")
    click.echo(f"Projection DB: {config.db_path}")
    if created:
        click.echo("Initialized portable storage structure")
    click.echo(f"Imports processed: {result.entries_processed}")
    for entry_type, count in sorted(result.entries_by_type.items()):
        click.echo(f"  {entry_type}: {count}")


@db.command("rebuild")
def db_rebuild():
    """Rebuild the SQLite projection from the archived ingest log."""
    config = VaultConfig()
    created = ensure_vault_initialized(config)
    result = replay_vault(config)

    click.echo(f"Vault: {config.path}")
    click.echo(f"Projection DB: {config.db_path}")
    if created:
        click.echo("Initialized portable storage structure")
    click.echo("Rebuilt projection from vault log")
    click.echo(f"Imports processed: {result.entries_processed}")
    for entry_type, count in sorted(result.entries_by_type.items()):
        click.echo(f"  {entry_type}: {count}")


@db.command("drop")
def db_drop():
    """Delete the SQLite projection database after confirmation."""
    config = VaultConfig()
    db_path = config.db_path

    click.echo(f"Projection DB: {db_path}")
    click.confirm("Drop the SQLite projection database?", abort=True)

    init_db(None)
    if db_path.exists():
        db_path.unlink()
        click.echo("Dropped projection database.")
    else:
        click.echo("Projection database did not exist.")


@log.command("list")
def log_list():
    """List archived ingest log entries."""
    config = VaultConfig()
    ledger = Ledger(config.path)
    entries = ledger.read_entries()

    if not entries:
        click.echo("No log entries found.")
        return

    click.echo("Seq    Timestamp             Type    Parser      Files  Contents")
    for entry in entries:
        parser = entry.record.get("parser", "-")
        files = entry.record.get("csv_files", [])
        type_name = entry.entry_type
        contents = ", ".join(files) if files else "-"
        click.echo(
            f"{entry.sequence:<6} "
            f"{entry.timestamp:<20} "
            f"{type_name:<7} "
            f"{parser:<11} "
            f"{len(files):<5} "
            f"{contents}"
        )


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

    detection = parser.detect(csv_file.name, content)
    existing_account = find_account_by_bank_account_number(
        detection.bank, detection.bank_account_number, include_hidden=False
    )

    if dry_run:
        account_id = existing_account.id if existing_account is not None else 0
        account_label = (
            f"#{existing_account.id} ({existing_account.bank} {detection.bank_account_number})"
            if existing_account is not None
            else f"[new] ({detection.bank} {detection.bank_account_number})"
        )
    else:
        account_id = existing_account.id if existing_account is not None else 0
        account_label = (
            f"#{existing_account.id} ({existing_account.bank} {detection.bank_account_number})"
            if existing_account is not None
            else f"[new] ({detection.bank} {detection.bank_account_number})"
        )

    parsed_transactions = parser.parse(csv_file.name, content, account_id=account_id)
    section_counts = Counter(transaction.subaccount_type for transaction in parsed_transactions)
    sections_text = (
        ", ".join(f"{section} ({count})" for section, count in sorted(section_counts.items()))
        or "-"
    )

    if dry_run:
        click.echo(f"Detected: {detection.parser_name}")
        click.echo(f"Account: {account_label}")
        click.echo(f"Sections: {sections_text}")
        click.echo(f"Parsed: {len(parsed_transactions)} transactions")
        for transaction in parsed_transactions[:5]:
            click.echo(
                f"  {transaction.date.isoformat()} | "
                f"{transaction.payee[:30]:<30} | {transaction.amount_cents / 100:>8.2f}"
            )
        return

    result = ingest_vault_csv(
        IngestRequest(
            filename=csv_file.name,
            content=csv_file.read_bytes(),
            csv_type=csv_type,
        )
    )

    try:
        run_stored_rules(ensure_rules=True, include_hidden=True)
    except Exception as exc:
        raise click.ClickException(
            f"Import stored transactions, but rules evaluation failed: {exc}"
        ) from exc

    click.echo(f"Detected: {result.parser_name}")
    click.echo(
        f"Account: #{result.account_id} ({result.account_bank} {detection.bank_account_number})"
    )
    click.echo(
        "Sections: "
        + ", ".join(f"{section} ({count})" for section, count in sorted(result.sections.items()))
    )

    click.echo("")
    click.echo("Importing...")
    click.echo(f"  New: {result.transactions_new} transactions")
    click.echo(f"  Duplicates: {result.transactions_duplicate} (skipped)")
    click.echo("")
    click.echo("Done.")


@main.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host")
@click.option("--port", default=8000, show_default=True, type=int, help="Bind port")
def serve(host: str, port: int):
    """Start the Penny web server."""

    run_server(host=host, port=port)


@transactions.command("list")
@click.option(
    "--from", "from_date", type=click.DateTime(formats=["%Y-%m-%d"]), help="Start date (inclusive)"
)
@click.option(
    "--to", "to_date", type=click.DateTime(formats=["%Y-%m-%d"]), help="End date (inclusive)"
)
@click.option(
    "--account",
    "-a",
    "account_ids",
    multiple=True,
    type=int,
    help="Filter by account ID (repeatable)",
)
@click.option("--category", help="Filter by category prefix")
@click.option("--query", "-q", help="Search booking text or payee")
@click.option("--tab", type=click.Choice(["expense", "income"]), help="Filter by amount sign")
@click.option(
    "--neutralize/--no-neutralize",
    default=True,
    show_default=True,
    help="Collapse transfer groups to net sums",
)
@click.option("--limit", "-n", type=int, help="Number of transactions to show")
def transactions_list(
    from_date: datetime | None,
    to_date: datetime | None,
    account_ids: tuple[int, ...],
    category: str | None,
    query: str | None,
    tab: str | None,
    neutralize: bool,
    limit: int | None,
):
    """List recent transactions."""

    transaction_list = list_transactions(
        filters=_build_transaction_filter(
            from_date=from_date,
            to_date=to_date,
            account_ids=account_ids,
            category=category,
            query=query,
            tab=tab,
        ),
        limit=limit,
        neutralize=neutralize,
    )
    if not transaction_list:
        click.echo("No transactions found.")
        return

    for transaction in transaction_list:
        click.echo(
            f"{transaction.date.isoformat()} | "
            f"{transaction.payee[:25]:<25} | {transaction.amount_cents / 100:>10.2f} | "
            f"{transaction.category or '-'}"
        )


@main.command("report")
@click.option(
    "--from", "from_date", type=click.DateTime(formats=["%Y-%m-%d"]), help="Start date (inclusive)"
)
@click.option(
    "--to", "to_date", type=click.DateTime(formats=["%Y-%m-%d"]), help="End date (inclusive)"
)
@click.option(
    "--account",
    "-a",
    "account_ids",
    multiple=True,
    type=int,
    help="Filter by account ID (repeatable)",
)
@click.option("--category", help="Filter by category prefix")
@click.option("--query", "-q", help="Search booking text or payee")
def report(
    from_date: datetime | None,
    to_date: datetime | None,
    account_ids: tuple[int, ...],
    category: str | None,
    query: str | None,
):
    """Generate the plain text finance report."""

    click.echo(
        generate_report_text(
            _build_transaction_filter(
                from_date=from_date,
                to_date=to_date,
                account_ids=account_ids,
                category=category,
                query=query,
            )
        )
    )


@main.command("apply")
@click.argument("rules_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-v", "verbose", count=True, help="Increase verbosity (-v result lines, -vv rule trace)"
)
def apply(rules_file: Path, verbose: int):
    """Apply classification rules and optional transfer linking."""

    _apply_rules(rules_file, verbose=verbose)


@main.command("import-rules")
@click.argument("rules_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def import_rules(rules_file: Path):
    """Import a rules.py file into the vault.

    The rules file will be copied to the vault's rules directory with a timestamp.
    This makes it the active rules file for classification.
    """
    content = rules_file.read_text(encoding="utf-8")

    # Validate the rules file by attempting to load it
    try:
        config, _module = _load_rules_bundle(rules_file)
        click.echo(f"Validated: {len(config.ruleset.rules)} rules loaded")
        click.echo(f"Default category: {config.default_category}")
    except Exception as exc:
        raise click.ClickException(f"Invalid rules file: {exc}") from exc

    # Save to vault
    saved_path = save_rules_snapshot(content)
    click.echo(f"Saved to: {saved_path}")
    click.echo("Rules imported successfully.")


if __name__ == "__main__":
    main()
