import { defineConfig } from '@playwright/test';

const PORT = process.env.PENNY_UI_TEST_PORT || '9321';
const RUN_ID = process.env.PENNY_UI_TEST_RUN_ID || `${Date.now()}`;

export default defineConfig({
  testDir: '.',
  timeout: 60_000,
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'on-first-retry',
  },
  webServer: {
    command: `uv run python -c "from penny.server import run_server; run_server(port=${PORT})"`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    timeout: 60_000,
    reuseExistingServer: true,
    env: {
      PENNY_VAULT_DIR: `.playwright/penny-${PORT}-${RUN_ID}`,
    },
  },
});
