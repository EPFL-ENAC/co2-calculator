/**
 * Regression test for #2570 — a user with valid roles is dumped on
 * /unauthorized when their persisted workspace selection points at a unit they
 * may read but not enter.
 *
 * Seen on stage after the database was dropped and reseeded: unit ids moved,
 * and every returning user's `workspaceLocalStorage` still named the old one.
 * Trace 029247:
 *
 *   GET /v1/units/996                 200   <- unit probe SUCCEEDS
 *   GET /v1/workspace/996/2025/home   403   <- workspace load REFUSED
 *
 * Root cause: `fetchWorkspaceHome` (stores/workspace.ts) issued its request
 * without `skipErrorCodes`, so the afterResponse hook in api/http.ts treated
 * the 403 as a page-access denial — toast + hard location.replace to
 * /unauthorized — and won the race against the guard's own soft redirect to
 * the landing resolver. #2369 gave the sibling `getUnit` call exactly this
 * treatment; the same guard's second probe was missed.
 *
 * The stale selection is only the trigger. Any unit a user can read but not
 * enter reproduces it, with or without a database drop.
 */
import { test, expect } from '@playwright/test';
import {
  mockRefusedWorkspaceBackend,
  STALE_WORKSPACE_URL,
  EXPECTED_URL_PATTERN,
} from './setup/workspace-refused-unit-mocks';

test.describe('workspace guard — a refused unit redirects, never /unauthorized (#2570)', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      try {
        localStorage.clear();
      } catch {
        // Some contexts restrict localStorage before first load; ignore.
      }
    });
  });

  test('a stale selection whose workspace is refused lands on the user own unit, not /unauthorized', async ({
    page,
  }) => {
    const { requests } = await mockRefusedWorkspaceBackend(page);

    await page.goto(STALE_WORKSPACE_URL);

    // The guard's soft redirect: the landing resolver picks the user's first
    // unit and the most recent open year. Before the fix this was
    // /unauthorized instead.
    await expect(page).toHaveURL(EXPECTED_URL_PATTERN);
    await expect(page).not.toHaveURL(/unauthorized/);

    // No "Permission denied" toast either: a refusal on this path is data the
    // guard acts on, not an error to show the user.
    await expect(page.locator('.q-notification')).toHaveCount(0);

    // The refused call really was made — otherwise this test would pass for
    // the wrong reason if the guard stopped probing altogether.
    expect(
      requests.some((r) => r.url.includes('/workspace/996/2025/home')),
    ).toBe(true);
  });
});
