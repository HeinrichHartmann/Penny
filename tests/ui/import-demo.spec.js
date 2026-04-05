import { expect, test } from '@playwright/test';

test('demo import journey keeps core views populated', async ({ page }) => {
  const uiTimeoutMs = 1_000;
  const firstTransactionDate = () => page.locator('tbody tr').first().locator('td').first();
  const firstBalanceTransactionDate = () => page.locator('main table').last().locator('tbody tr').first().locator('td').first();
  const balanceChartCanvas = () => page.locator('canvas').first();

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
  await expect.soft(page.getByText(/Last run:/)).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Matched', { exact: true })).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Unmatched', { exact: true })).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Save rules or click "Run Classification" to see results')).toHaveCount(0, { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Transactions' }).click();
  await expect(page.getByRole('heading', { name: 'Transactions', exact: true })).toBeVisible();
  await expect.soft(page.getByRole('button', { name: '2024' })).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByRole('button', { name: '2023' })).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByRole('button', { name: '2022' })).toBeVisible({ timeout: uiTimeoutMs });

  await page.getByRole('button', { name: '2024' }).click();
  await expect.soft(page.locator('input[type="date"]').first()).toHaveValue('2024-01-01', { timeout: uiTimeoutMs });
  await expect.soft(page.locator('input[type="date"]').nth(1)).toHaveValue('2024-12-31', { timeout: uiTimeoutMs });
  await expect.soft(firstTransactionDate()).toContainText('2024-03-29', { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: '2023' }).click();
  await expect.soft(page.locator('input[type="date"]').first()).toHaveValue('2023-01-01', { timeout: uiTimeoutMs });
  await expect.soft(page.locator('input[type="date"]').nth(1)).toHaveValue('2023-12-31', { timeout: uiTimeoutMs });
  await expect.soft(firstTransactionDate()).toContainText('2023-12-29', { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: '2022' }).click();
  await expect.soft(page.locator('input[type="date"]').first()).toHaveValue('2022-01-01', { timeout: uiTimeoutMs });
  await expect.soft(page.locator('input[type="date"]').nth(1)).toHaveValue('2022-12-31', { timeout: uiTimeoutMs });
  await expect.soft(firstTransactionDate()).toContainText('2022-12-29', { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'All', exact: true }).first().click();
  await page.getByPlaceholder('Search description').fill('Sparen');
  await expect.soft(page.locator('tbody tr').first()).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Showing 1-24 of 24')).toBeVisible({ timeout: uiTimeoutMs });
  await expect.soft(page.locator('tbody tr').nth(9)).toContainText('2023-06-29', { timeout: uiTimeoutMs });
  await expect.soft(page.locator('tbody tr').nth(9).locator('td').nth(2)).toContainText('Sparen', { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Report' }).click();
  await expect(page.getByRole('heading', { name: 'Report', exact: true })).toBeVisible();
  await expect.soft(page.getByText('Expenses')).toBeVisible({ timeout: uiTimeoutMs });
  await page.locator('[data-tab="report"]').click();
  await expect.soft(page.locator('pre.report-text')).not.toHaveText('Loading...', { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Balance' }).click();
  await expect(page.getByRole('heading', { name: 'Account Balance History' })).toBeVisible();
  await expect.soft(page.getByText('No balance data available for the selected accounts and date range.')).toHaveCount(0, { timeout: uiTimeoutMs });
  await expect.soft(page.getByText('Recorded Balance Snapshots')).toBeVisible({ timeout: uiTimeoutMs });

  await expect.soft(balanceChartCanvas()).toBeVisible({ timeout: uiTimeoutMs });

  await page.getByRole('button', { name: '2024' }).click();
  await expect.soft(page.locator('input[type="date"]').first()).toHaveValue('2024-01-01', { timeout: uiTimeoutMs });
  await expect.soft(page.locator('input[type="date"]').nth(1)).toHaveValue('2024-12-31', { timeout: uiTimeoutMs });

  await page.getByRole('button', { name: 'Mar' }).click();
  await expect.soft(page.locator('input[type="date"]').first()).toHaveValue('2024-03-01', { timeout: uiTimeoutMs });
  await expect.soft(page.locator('input[type="date"]').nth(1)).toHaveValue('2024-03-31', { timeout: uiTimeoutMs });
  await expect.soft(firstBalanceTransactionDate()).toContainText('2024-03-', { timeout: uiTimeoutMs });
  const marchFirstBalanceDate = (await firstBalanceTransactionDate().textContent())?.trim();
  const marchChartImage = await balanceChartCanvas().evaluate((canvas) => canvas.toDataURL());

  await page.getByRole('button', { name: 'Feb' }).click();
  await expect.soft(page.locator('input[type="date"]').first()).toHaveValue('2024-02-01', { timeout: uiTimeoutMs });
  await expect.soft(page.locator('input[type="date"]').nth(1)).toHaveValue('2024-02-29', { timeout: uiTimeoutMs });
  await expect.soft(firstBalanceTransactionDate()).toContainText('2024-02-', { timeout: uiTimeoutMs });
  const februaryFirstBalanceDate = (await firstBalanceTransactionDate().textContent())?.trim();
  expect(februaryFirstBalanceDate).not.toBe(marchFirstBalanceDate);
  await page.waitForFunction((previousImage) => {
    const canvas = document.querySelector('canvas');
    return Boolean(canvas) && canvas.toDataURL() !== previousImage;
  }, marchChartImage);
});
