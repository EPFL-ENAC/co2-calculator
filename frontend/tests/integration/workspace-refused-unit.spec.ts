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

/**
 * Second failure mode, and the reason the fix above is not sufficient on its
 * own: the guard's soft redirect targets the landing resolver, and
 * `redirectToDefaultRoute` picks `workspaceStore.units[0]` deterministically.
 * If THAT unit's workspace also fails — 403, or a 200 carrying
 * `carbon_report_id: null`, which lands in the same `!response ||
 * !carbonReportId` branch — the resolver hands back the same unit and the
 * guard redirects again. Unbounded.
 *
 * Note this is NOT reachable through a stale localStorage selection:
 * `redirectToDefaultRoute` never reads `selectedParams`. A stale selection
 * costs one wasted round trip and then resolves. The bounce needs the default
 * unit itself to be unusable.
 *
 * Before #2570 this was masked: the 403 hard-redirected to /unauthorized from
 * the HTTP layer, which was a dead end but terminated. Making the refusal soft
 * is what exposes it.
 */

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

    // The refused unit must not survive as "where you were": it is the only
    // persisted field, and ErrorNotFound's home link reads it back on a page
    // where no guard runs to refresh it. After the redirect it holds the unit
    // the user actually landed on, never 996.
    const persisted = await page.evaluate(() =>
      localStorage.getItem('workspaceLocalStorage'),
    );
    expect(persisted ?? '').not.toContain('996');
  });

  test('a user whose own default unit is also refused lands somewhere terminal instead of bouncing', async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    const { ownUnitHomeCalls } = await mockRefusedWorkspaceBackend(page, {
      refuseOwnUnit: true,
    });

    await page.goto(STALE_WORKSPACE_URL);

    // The app must settle. /unauthorized is the honest destination: the user
    // has no workspace they can open, and that is a state to show, not to
    // retry.
    await expect(page).toHaveURL(/unauthorized/, { timeout: 15000 });

    // The guard may try the resolver's pick once. Trying it repeatedly is the
    // bug: the resolver is deterministic, so every retry asks the same
    // question and gets the same answer.
    expect(ownUnitHomeCalls()).toBeLessThanOrEqual(2);

    // vue-router aborts a redirect cycle with this, which is what an
    // unbounded bounce looks like from the outside.
    expect(
      consoleErrors.filter((e) => /infinite redirection/i.test(e)),
    ).toHaveLength(0);
  });
});
