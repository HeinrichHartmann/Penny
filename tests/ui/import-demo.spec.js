import { expect, test } from '@playwright/test';

test('demo import journey keeps core views populated', async ({ page }) => {
  const uiTimeoutMs = 1_000;

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'Import', exact: true })).toBeVisible();

  const importDemoButton = page.getByRole('button', { name: 'Import Demo Data' });
  await expect(importDemoButton).toBeVisible();
  await importDemoButton.click();

  await expect(page.getByRole('heading', { name: 'Import History' })).toBeVisible();
  await expect(importDemoButton).toHaveCount(0);
  await expect(page.getByText('balance-anchors.tsv')).toBeVisible();
  await expect(page.getByText(/rules\.py$/)).toBeVisible();

  await page.getByRole('button', { name: 'Accounts' }).click();
  await expect(page.getByRole('heading', { name: 'Accounts', exact: true })).toBeVisible();
  await expect.soft(page.getByText('Balance:').first()).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByText(/\b[1-9]\d* transactions\b/).first()).toBeVisible({ timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Rules' }).click();
  await expect(page.getByRole('heading', { name: 'Classification Rules' })).toBeVisible();
  await expect.soft(page.getByText('Matched', { exact: true })).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Unmatched', { exact: true })).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Save rules or click "Run Classification" to see results')).toHaveCount(0, { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Transactions' }).click();
  await expect(page.getByRole('heading', { name: 'Transactions', exact: true })).toBeVisible();
  await expect.soft(page.locator('tbody tr').first()).toBeVisible({ timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Report' }).click();
  await expect(page.getByRole('heading', { name: 'Report', exact: true })).toBeVisible();
  await expect.soft(page.getByText('Expenses')).toBeVisible({ timeout: uiTimeoutMs });
  await page.locator('[data-tab="report"]').click();
  await expect.soft(page.locator('pre.report-text')).not.toHaveText('Loading...', { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Balance' }).click();
  await expect(page.getByRole('heading', { name: 'Account Balance History' })).toBeVisible();
  await expect.soft(page.getByText('No balance data available for the selected accounts and date range.')).toHaveCount(0, { timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Recorded Balance Snapshots')).toBeVisible({ timeout: uiTimeoutMs });
});
