# Testing Strategy

Penny currently uses two test styles.

## 1. Unit Tests

Location:
- `tests/unit/`

Rules:
- Run inside a single Python process.
- Use direct function and object calls. Never shell out processes or call CLI or REST endpoints. Call the handler methods.
- If database state is needed, use a fresh in-memory DB via `init_db(None)`.
- Prefer in-memory buffers and literals for test data where the internal API allows it.
- Touch disk only when the behavior under test is inherently file-based and there is no cleaner in-memory seam.

Harness:
- `tests/unit/conftest.py` forces a fresh in-memory DB for every test.
- Temporary `PENNY_DATA_DIR` / `PENNY_VAULT_DIR` are still set so incidental file writes stay isolated.

Examples in this bucket:
- parser logic
- rule loading
- transaction filtering
- transfer grouping
- vault data structures that are tested directly as Python APIs

## 2. End-to-End Tests

Location:
- `tests/e2e/`

Rules:
- Exercise Penny through external boundaries: CLI commands, REST calls, startup/bootstrap flows, or real vault/projection state on disk.
- Each test gets a newly initialized file-backed runtime.
- Each runtime gets a fresh temporary vault/data directory and a freshly reserved localhost port, mirroring `make serve-fresh`.
- Use this layer to prove the app can spin up, import data, classify, replay, and expose the expected views and commands.

Harness:
- `tests/e2e/conftest.py` creates a new runtime per test and initializes the default file-backed DB.
- `fresh_runtime` is available for tests that need the temporary directories or reserved port explicitly.

Coverage goals for this layer:
- spin up a server
- import the demo data
- import supported CSV formats
- render the basic backend-served views and API responses

## Frontend Policy

There is currently no automated frontend test suite.

For now:
- keep frontend logic intentionally light
- validate frontend behavior manually
- optionally use an LLM assistant with a browser tool such as Chrome MCP for exploratory checks

The automated suite should focus on backend correctness, import reproducibility, and stable app interfaces.

## 3. UI Tests

Location:
- `tests/ui/`

Rules:
- UI tests are Playwright-native, not `pytest`-based.
- Use them for real browser journeys and frontend wiring regressions.
- Keep them focused on user-visible flows such as initial load, import actions, navigation, and visible state changes.

Execution:
- `npm run test:ui`
- `make test` also runs the Playwright UI suite after the Python tests

Environment:
- The flake shell provides the Playwright browser bundle declaratively.
- UI tests should not depend on `playwright install` at runtime.
- The npm `@playwright/test` version must stay aligned with the `playwright-driver` version provided by `flake.nix`.
- Run `make` from within the direnv/flake environment rather than invoking `direnv` inside `Makefile`.

## Transitional State

Most cleanly separated files are being moved under `tests/unit/` or `tests/e2e/`.

These top-level files are intentionally left in place for now because they mix both styles and should be split in a follow-up pass:
- `tests/test_accounts.py`
- `tests/test_classify.py`
- `tests/test_import_detection.py`

Top-level mixed files currently rely on the root `tests/conftest.py`:
- unmarked tests run with an in-memory DB
- tests marked `integration` run with a fresh file-backed runtime

## Current Audit

Unit bucket is in decent shape:
- most parser, rule, filtering, and transfer tests fit the single-process model well
- some unit tests still read CSV fixtures from disk; that is acceptable short-term, but several could later migrate to in-memory buffers
- some vault structure tests still use temporary directories because the behavior is explicitly file-based

End-to-end bucket is partially consistent:
- CLI, API, replay, startup, and import tests belong here
- the runtime fixture now provides fresh directories and a fresh port per test
- a few root-level mixed files still need to be split so the folder structure becomes the only source of truth

Follow-up work to finish the migration:
1. Split the remaining mixed top-level files into separate unit and e2e files.
2. Replace disk fixture reads with in-memory buffers where the relevant internal API supports it cleanly.
3. Add a true subprocess-backed server smoke test that uses `fresh_runtime.port` rather than only `TestClient`.
