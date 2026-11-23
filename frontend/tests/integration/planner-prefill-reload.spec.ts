/**
 * Regression test for issue #2778: reloading the Project Planner while the
 * year prefill job runs dropped the "prefill running" banner and let the
 * user edit years the job was about to wipe and rebuild.
 *
 * Only the PATCH that queued the job returned its id. The fix has GET on the
 * plan report the unfinished job too, and the page waits on it with the year
 * sections locked (`inert`), exactly as after the PATCH.
 *
 * The prefill status is stateful: it stays unfinished across a reload, then
 * `finishPrefill()` ends it and the page must unlock and refetch the years.
 */
import { test, expect, type Page } from 'playwright/test';
import {
  installExplorerInitScripts,
  mockExplorerBackend,
  REPORT_STATS,
  UNIT_ID,
  YEAR,
} from './setup/simulator-mocks';

const PLAN_ID = 7;
const JOB_ID = 77;
const PLANNER_URL = `/en/${UNIT_ID}/${YEAR}/simulation/plan/${PLAN_ID}`;

function json(body: unknown) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

async function mockPlannerPrefill(page: Page) {
  let prefillDone = false;
  const context = page.context();

  await context.route(
    new RegExp(`/api/v1/project-plans/${PLAN_ID}(\\?.*)?$`),
    (route) =>
      route.fulfill(
        json({
          id: PLAN_ID,
          unit_id: UNIT_ID,
          name: 'Plan under prefill',
          start_year: 2027,
          end_year: 2027,
          is_viewable_by_unit_members: false,
          is_grant_proposal: false,
          created_by: 1,
          created_at: '2026-01-01T00:00:00Z',
          creator_name: 'Principal User',
          total_tonnes_co2eq: null,
          grant_total_tonnes_co2eq: null,
          prefill_job_id: prefillDone ? null : JOB_ID,
        }),
      ),
  );
  await context.route(
    new RegExp(`/api/v1/project-plans/${PLAN_ID}/prefill/${JOB_ID}$`),
    (route) =>
      route.fulfill(
        json({
          job_id: JOB_ID,
          finished: prefillDone,
          result: prefillDone ? 'success' : null,
          status_message: null,
        }),
      ),
  );
  await context.route(
    new RegExp(`/api/v1/project-plans/${PLAN_ID}/years$`),
    (route) =>
      route.fulfill(
        json([
          {
            id: 501,
            year: 2027,
            reference_year: YEAR,
            is_grant: false,
            budget: null,
            budget_currency: null,
            stats: null,
            modules: [],
            factor_year: YEAR,
          },
        ]),
      ),
  );
  await context.route(
    new RegExp(`/api/v1/project-plans/${PLAN_ID}/aggregate-stats$`),
    (route) => route.fulfill(json({ years: REPORT_STATS, grant: null })),
  );

  return {
    finishPrefill: () => {
      prefillDone = true;
    },
  };
}

test.describe('project planner — reload during the year prefill (#2778)', () => {
  test('the banner and the edit lock survive a reload until the prefill ends', async ({
    page,
  }) => {
    await installExplorerInitScripts(page.context());
    const { requests } = await mockExplorerBackend(page);
    const { finishPrefill } = await mockPlannerPrefill(page);

    const banner = page.getByTestId('planner-prefill-running');
    const sections = page.getByTestId('planner-year-sections');
    const projectInfo = page.getByTestId('planner-project-info');

    await page.goto(PLANNER_URL);
    await expect(banner).toBeVisible();
    await expect(sections).toHaveAttribute('inert');
    await expect(projectInfo).toHaveAttribute('inert');

    await page.reload();
    await expect(banner).toBeVisible();
    await expect(sections).toHaveAttribute('inert');
    await expect(projectInfo).toHaveAttribute('inert');

    const yearFetches = () =>
      requests.filter((r) => r.url.endsWith(`/project-plans/${PLAN_ID}/years`))
        .length;
    const yearFetchesBefore = yearFetches();

    finishPrefill();

    await expect(banner).toBeHidden({ timeout: 10_000 });
    await expect(sections).not.toHaveAttribute('inert');
    await expect(projectInfo).not.toHaveAttribute('inert');
    await expect.poll(yearFetches).toBeGreaterThan(yearFetchesBefore);
  });
});
