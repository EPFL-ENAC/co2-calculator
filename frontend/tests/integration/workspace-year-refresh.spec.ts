/**
 * Regression test for issue #1558 — after a backoffice admin opens a
 * reporting year ("Open year for users" flips `is_started` to true), the
 * calculator's year selector doesn't show the newly-opened year until the
 * page is hard-reloaded (Ctrl+R / F5).
 *
 * Root cause: `yearConfigStore.configuredYears` (which drives `startedYears`
 * → the WorkspaceSelectorBar year dropdown, see workspace-selector/
 * WorkspaceSelectorBar.vue `yearOptions`) was hydrated once at auth
 * bootstrap (`GET /session`) and only ever refetched by the workspace guard
 * / landing resolver when it was still empty — which is never true again
 * once bootstrap has populated it. A backoffice year-open action happening
 * mid-session therefore never reached the calculator until a full reload
 * rebuilt Pinia state from scratch.
 *
 * Fix: `loadWorkspaceFromRoute` (workspaceGuard.ts) and `fetchStartedYears`
 * (redirectToDefaultRoute.ts) now call `fetchConfiguredYears()`
 * unconditionally on every run, mirroring how `fetchWorkspaceHome` already
 * refreshes on every guard run.
 *
 * This test mocks the year-configuration list as stateful (2025 starts
 * closed, then "opens" mid-test) and asserts the year dropdown picks up the
 * change on the next in-app navigation — a unit switch via the
 * WorkspaceSelectorBar — WITHOUT any page reload. A test that only checked
 * behavior after `page.reload()` would not catch this class of bug.
 */
import { test, expect } from '@playwright/test';
import {
  mockWorkspaceBackend,
  WORKSPACE_URL,
} from './setup/workspace-year-refresh-mocks';

test.describe('workspace year selector — refetches on in-app navigation (#1558)', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.clear();
      } catch {
        // Some contexts restrict localStorage before first load; ignore.
      }
    });
  });

  test('a year opened via the backoffice mid-session appears in the year dropdown after switching units in-app, without a page reload', async ({
    page,
  }) => {
    const { requests, openYear2025ForUsers } = await mockWorkspaceBackend(page);

    await page.goto(WORKSPACE_URL);

    const unitSelect = page.getByTestId('workspace-unit-select');
    const yearSelect = page.getByTestId('workspace-year-select');
    await expect(unitSelect).toBeVisible();

    // Baseline: only 2024 is open, so only 2024 is offered.
    await yearSelect.click();
    await expect(
      page.locator('.q-menu .q-item', { hasText: '2024' }),
    ).toBeVisible();
    await expect(
      page.locator('.q-menu .q-item', { hasText: '2025' }),
    ).toHaveCount(0);
    await page.keyboard.press('Escape');

    const yearConfigRequestsBefore = requests.filter((r) =>
      r.url.includes('/year-configuration/'),
    ).length;

    // Simulate an admin opening 2025 via the backoffice in another
    // tab/session — the next `GET /year-configuration/` call now returns it
    // as started.
    openYear2025ForUsers();

    // In-app navigation (no reload): switch to the second unit via the
    // WorkspaceSelectorBar. This changes the route's `:unit` param, which
    // re-runs the workspace guard and — with the fix — refetches
    // `configuredYears`.
    await unitSelect.click();
    await page.locator('.q-menu .q-item', { hasText: 'Unit Beta' }).click();
    await expect(page).toHaveURL(/\/20-unit-beta\//);

    // The year dropdown must now offer 2025 — reflecting the backend change
    // — without any page reload having occurred.
    await yearSelect.click();
    await expect(
      page.locator('.q-menu .q-item', { hasText: '2024' }),
    ).toBeVisible();
    await expect(
      page.locator('.q-menu .q-item', { hasText: '2025' }),
    ).toBeVisible();

    const yearConfigRequestsAfter = requests.filter((r) =>
      r.url.includes('/year-configuration/'),
    ).length;
    expect(yearConfigRequestsAfter).toBeGreaterThan(yearConfigRequestsBefore);
  });
});
