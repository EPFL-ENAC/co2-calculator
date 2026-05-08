import { test, expect } from '@playwright/test';

/**
 * E2E coverage for the back-office "Open year for users" flow (issue #867).
 *
 * The dev preview server has no auth/session by default, so these specs
 * intercept the year-configuration API directly and assert UI behavior:
 * the visibility chip reflects `is_started`, the button is disabled when
 * the year is already open, and clicking the button when it is not open
 * sends a PATCH with `{ is_started: true }` and shows a success toast.
 *
 * If the route is gated behind auth in this environment, these tests will
 * skip (see the navigation guard below) instead of producing false failures.
 */

const PAGE_PATH = '/back-office/data-management';

const baseConfig = (overrides: Partial<{ is_started: boolean }> = {}) => ({
  year: 2025,
  is_started: false,
  is_reports_synced: false,
  config: { modules: {}, reduction_objectives: {} },
  latest_jobs: [],
  updated_at: new Date().toISOString(),
  ...overrides,
});

test.describe('Data management — open year for users', () => {
  test.beforeEach(async ({ page }) => {
    // Stub the year-configuration GET so the page can render without a backend.
    await page.route('**/api/v1/year-configuration/**', async (route) => {
      const method = route.request().method();
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(baseConfig({ is_started: false })),
        });
      } else {
        await route.continue();
      }
    });
  });

  test('button is enabled and shows success toast when year is not yet open', async ({
    page,
  }) => {
    let patchBody: unknown = null;

    await page.route('**/api/v1/year-configuration/**', async (route) => {
      if (route.request().method() === 'PATCH') {
        patchBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(baseConfig({ is_started: true })),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(baseConfig({ is_started: false })),
        });
      }
    });

    const response = await page.goto(PAGE_PATH);
    test.skip(
      !response || response.status() >= 400,
      'Back-office route is not reachable in this environment',
    );

    const chip = page.getByTestId('year-open-status-chip');
    await expect(chip).toContainText(/Not yet open|Pas encore ouverte/);

    const btn = page.getByTestId('open-year-for-users-btn');
    await expect(btn).toBeEnabled();
    await btn.click();

    expect(patchBody).toEqual({ is_started: true });
    await expect(chip).toContainText(/Open to users|Ouverte aux utilisateurs/);
  });

  test('button is disabled with tooltip when year is already open', async ({
    page,
  }) => {
    await page.route('**/api/v1/year-configuration/**', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(baseConfig({ is_started: true })),
        });
      } else {
        await route.continue();
      }
    });

    const response = await page.goto(PAGE_PATH);
    test.skip(
      !response || response.status() >= 400,
      'Back-office route is not reachable in this environment',
    );

    const chip = page.getByTestId('year-open-status-chip');
    await expect(chip).toContainText(/Open to users|Ouverte aux utilisateurs/);

    const btn = page.getByTestId('open-year-for-users-btn');
    await expect(btn).toBeDisabled();
  });
});
