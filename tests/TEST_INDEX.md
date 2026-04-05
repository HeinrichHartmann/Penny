# Test Index

This file gives a high-level overview of the test suite layout and what each file covers.

## Shared Test Files

- `tests/TEST_STRATEGY.md`
  High-level testing policy for Penny. Describes the split between unit tests and end-to-end tests, the runtime model for each, and current testing goals.

- `tests/helpers.py`
  Shared helper utilities for test runtime setup, especially the fresh file-backed runtime used by end-to-end tests.

- `tests/fixtures/`
  Static sample inputs used by multiple tests, including CSV exports and rules files.

## Unit Tests

- `tests/unit/conftest.py`
  Unit-test harness. Forces an in-memory database and isolates incidental filesystem state.

- `tests/unit/test_accounts.py`
  Core account-domain behavior: creation, lookup, soft deletion, duplicate handling, and mutation logging.

- `tests/unit/test_buchungstext.py`
  Parsing helpers for payee, memo, and reference extraction from booking text.

- `tests/unit/test_classify.py`
  Classification helper behavior and ordered rule loading from Python rule modules.

- `tests/unit/test_comdirect_parser.py`
  Main Comdirect parser behavior on representative fixture input, including parsed transaction fields and fingerprint behavior.

- `tests/unit/test_comdirect_parser_edge_cases.py`
  Comdirect parser edge cases such as empty sections and split Visa rows.

- `tests/unit/test_import_detection.py`
  Import detection logic for Comdirect files, including filename validation and explicit parser selection.

- `tests/unit/test_ledger.py`
  Ledger entry and ledger file behavior, including sequencing, reads, updates, and file layout helpers.

- `tests/unit/test_rules_module.py`
  Loading of the bundled default rules module and basic expectations about its contents.

- `tests/unit/test_sparkasse_parser.py`
  Sparkasse parser detection and parsing behavior on representative fixture input.

- `tests/unit/test_transaction_filters.py`
  Reusable transaction filtering logic and filtered transaction listing behavior.

- `tests/unit/test_transfers.py`
  Transfer-grouping logic, grouping heuristics, and consolidated transaction behavior.

- `tests/unit/test_vault.py`
  Low-level vault configuration, mutation log, rules snapshot, and ledger-related API behavior.

## End-to-End Tests

- `tests/e2e/conftest.py`
  End-to-end harness. Creates a fresh file-backed Penny runtime for each test and initializes the on-disk projection database.

- `tests/e2e/test_accounts.py`
  Account management through the CLI, including add, list, remove, and hidden-account display.

- `tests/e2e/test_apply.py`
  Rule application through the CLI, including verbose output, trace output, and transfer-linking integration.

- `tests/e2e/test_classify.py`
  End-to-end classification workflows through CLI and API entry points, including reclassification, default categories, replay, and invalid-rules failures.

- `tests/e2e/test_cli_help.py`
  CLI help output coverage for top-level commands and serve command options.

- `tests/e2e/test_cli_reports_and_filters.py`
  CLI-level reporting and filtering flows, checking that command behavior matches domain filtering expectations.

- `tests/e2e/test_dashboard_api.py`
  Dashboard API behavior for transaction filtering and hidden-account exclusion.

- `tests/e2e/test_demo_import_e2e.py`
  Demo-data import flow through the API, covering import history, transaction availability, report data, balance history, and automatic classification.

- `tests/e2e/test_import_detection.py`
  Import-related CLI behavior at the system boundary, including supported parser help and rejection of renamed files.

- `tests/e2e/test_import_integration.py`
  CSV import workflows through CLI and API paths, including deduplication, dry-run behavior, auto-classification, and invalid-rules handling.

- `tests/e2e/test_vault_cli.py`
  Vault and database CLI commands such as initialization, status, replay, rebuild, drop, and archived import listing.

- `tests/e2e/test_vault_ingest.py`
  Vault-backed ingest and replay flows using the real ledger and projection behavior across multiple ingest scenarios.

- `tests/e2e/test_vault_startup.py`
  Application startup bootstrap behavior, including vault initialization, replay, drift cleanup, mutation replay, and manual-account restoration.
