# UI Tests

This directory contains browser-level UI tests for Penny.

Current setup:
- Playwright is used as the browser harness.
- The config starts the Penny backend directly and points it at a fresh vault directory.
- The first smoke test only verifies that the app loads and that `Import Demo Data` can be clicked through successfully.
- Browser binaries are expected to come from the flake environment, not from `playwright install`.
- The npm `@playwright/test` version must match the `playwright-driver` version pinned in `flake.nix`.

Run inside the flake environment:

```bash
direnv exec . make test-ui
```

Notes:
- These tests assume the backend can serve the built frontend assets already present in the repo.
- The harness currently focuses on reproducing real user journeys, not component-level frontend testing.
