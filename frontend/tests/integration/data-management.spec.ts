/**
 * Plan 310 / Unit 10 — Playwright happy-path coverage for the
 * back-office data-management page.  Mocks the HTTP boundary
 * (``page.route``) and the SSE channel (``EventSource`` shim) so the
 * suite runs in CI without a backend dev server.
 *
 * One spec covers the seven click-through interactions documented in
 * ``DataManagementPage.vue`` + ``ModuleConfig.vue``.  Test 3 (sync units
 * refetch) is parked with ``test.fixme`` — the missing-refetch bug is
 * tracked in issue #1080.
 *
 * Issue #867 / U5 — additional `Data management — open year for users`
 * describe block at the bottom of this file covers the is_started chip
 * + button flow.  Reuses the same `@playwright/test` import.
 */
import { test, expect, type Page, type Route } from '@playwright/test';
import {
  DATA_MANAGEMENT_URL,
  TEST_PIPELINE_ID,
  buildYearConfig,
  installInitScripts,
  mockBackend,
} from './setup/data-management-mocks';

test.describe('back-office data-management — happy paths', () => {
  test.beforeEach(async ({ context }) => {
    await installInitScripts(context);
  });

  test('1 — year selector triggers GET /year-configuration/{year}', async ({
    page,
  }) => {
    const { requests } = await mockBackend(page);

    await page.goto(DATA_MANAGEMENT_URL);

    // Initial load fires GET for 2024 (URL query param).  Wait for
    // the year-config card to render so we know the watcher ran.
    await expect(page.getByText(/year configuration/i).first()).toBeVisible();

    const initialGets = requests.filter(
      (r) => r.method === 'GET' && /year-configuration\/2024$/.test(r.url),
    );
    expect(initialGets.length).toBeGreaterThanOrEqual(1);

    // Switch the q-select to 2025.  Quasar renders the popup outside
    // the page in ``document.body``; ``getByRole('option')`` finds it.
    await page.locator('.q-select').first().click();
    await page.getByRole('option', { name: '2025' }).click();

    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.method === 'GET' && /year-configuration\/2025$/.test(r.url),
          ).length,
      )
      .toBeGreaterThanOrEqual(1);
  });

  test('2 — create year happy path: POST /year-configuration/{year} on missing config', async ({
    page,
  }) => {
    const { requests } = await mockBackend(page, {
      onGetYearConfig: notFoundThen200(),
    });

    await page.goto(DATA_MANAGEMENT_URL);

    // The "Create year" button is rendered when notFound=true.
    const createBtn = page.getByRole('button', {
      name: /create year/i,
    });
    await expect(createBtn).toBeVisible();

    // Issue #867 — the 404 from year-configuration GET is an expected
    // empty-state, not a user-facing error. The store opts out via
    // ``skipErrorCodes: [404]`` so no error toast should appear on landing.
    // (``bg-negative`` is the Quasar utility class applied by
    // ``Notify.create({ color: 'negative' })``.)
    await expect(page.locator('.q-notification.bg-negative')).toHaveCount(0);

    await createBtn.click();

    // POST must hit the singular-form endpoint.
    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.method === 'POST' && /year-configuration\/2024$/.test(r.url),
          ).length,
      )
      .toBe(1);

    // Cards re-render — wait for the success notification to surface
    // (Quasar Notify portals to ``body``).
    await expect(page.getByText(/configuration created/i)).toBeVisible({
      timeout: 5000,
    });
  });

  test('2b — create year already-exists: backend 409 surfaces error notification', async ({
    page,
  }) => {
    await mockBackend(page, {
      onGetYearConfig: notFoundThen200(),
      onCreateYear: async (route) => {
        await route.fulfill({
          status: 409,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'year already exists' }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    const createBtn = page.getByRole('button', {
      name: /create year/i,
    });
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // Expect a negative Notify with the backend's ``detail``-derived
    // message OR the i18n fallback ``Unknown error``.  ``ky`` throws
    // ``HTTPError`` with a non-empty ``message`` for non-2xx; the
    // page's catch surfaces it.  Match either the raw detail or
    // anything that looks like a notification toast.
    await expect
      .poll(async () => {
        const toasts = await page.locator('.q-notification').count();
        return toasts;
      })
      .toBeGreaterThan(0);
  });

  test('3 — create year auto-triggers unit_sync pipeline and refetches on FINISHED (#867)', async ({
    page,
  }) => {
    // Issue #867 — the standalone "Sync units from Accred" button is
    // gone; year creation now mints a ``pipeline_id`` on the create
    // response and the page subscribes to its SSE stream.  Verify the
    // full chain end-to-end:
    //
    //   1. POST /year-configuration/2024 fires once.
    //   2. The page opens an EventSource against the pipeline_id.
    //   3. Module config is gated (``inert``) while the pipeline is
    //      in flight.
    //   4. A fake ``pipeline-update`` with every job FINISHED un-gates
    //      the page, surfaces the success toast, and triggers a
    //      year-configuration GET.
    const { requests } = await mockBackend(page, {
      onGetYearConfig: notFoundThen200(),
    });

    await page.goto(DATA_MANAGEMENT_URL);

    const createBtn = page.getByRole('button', { name: /create year/i });
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // (1) POST fires exactly once and returns ``pipeline_id``.
    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.method === 'POST' && /year-configuration\/2024$/.test(r.url),
          ).length,
      )
      .toBe(1);

    // (2) Page issues the one-shot snapshot read against
    // ``GET /sync/pipelines/{id}`` (seed) before opening the SSE.
    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.method === 'GET' &&
              r.url.endsWith(`/api/v1/sync/pipelines/${TEST_PIPELINE_ID}`),
          ).length,
      )
      .toBeGreaterThanOrEqual(1);

    // (2') The EventSource constructor in ``installInitScripts``
    // registers itself on ``window.__sse``.  Verify the page opened
    // the stream for our pipeline_id.
    await expect
      .poll(() =>
        page.evaluate(
          (id) =>
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            (window as any).__sse?.sources.has(id) === true,
          TEST_PIPELINE_ID,
        ),
      )
      .toBe(true);

    // (3) Modules section should be ``inert`` while in flight.
    await expect(
      page.locator('div[inert].relative-position').first(),
    ).toBeVisible();

    // Track the GET count BEFORE we emit the FINISHED event so we
    // can assert it grows on completion (not just the count from
    // the create-then-watch flow).
    const getsBefore = requests.filter(
      (r) => r.method === 'GET' && /year-configuration\/2024$/.test(r.url),
    ).length;

    // (4) Drive the FINISHED event.  Single job, FINISHED+SUCCESS;
    // ``stream_closed: true`` for symmetry with the backend's
    // terminal payload.
    await page.evaluate(
      ({ id }) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (window as any).__sse.emit(id, {
          pipeline_id: id,
          jobs: [
            {
              id: 1,
              job_type: 'unit_sync',
              state: 'FINISHED',
              result: 'SUCCESS',
              status_message: 'ok',
              started_at: '2024-01-01T00:00:00Z',
              finished_at: '2024-01-01T00:01:00Z',
            },
          ],
          stream_closed: true,
        });
      },
      { id: TEST_PIPELINE_ID },
    );

    // (4a) Page un-gates: the ``inert`` wrapper either flips off or
    // is removed.  Use ``not.toHaveAttribute`` to tolerate either.
    await expect(async () => {
      const wrapper = page.locator('div.relative-position').first();
      const inertAttr = await wrapper.getAttribute('inert');
      // Vue serializes ``:inert="false"`` by removing the attribute.
      expect(inertAttr).toBeNull();
    }).toPass({ timeout: 5000 });

    // (4b) Year-configuration GET fires again to pick up the rows
    // the unit_sync handler upserted.
    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.method === 'GET' && /year-configuration\/2024$/.test(r.url),
          ).length,
      )
      .toBeGreaterThan(getsBefore);

    // (4c) Success toast surfaces.
    await expect(page.locator('.q-notification').first()).toBeVisible();
  });

  test('4 — CSV data upload: POST temp-upload + sync/dispatch with target_type=DATA_ENTRIES', async ({
    page,
  }) => {
    const { requests } = await mockBackend(page);
    await page.goto(DATA_MANAGEMENT_URL);

    await openHeadcountDataDialog(page);

    // Pick a CSV file.  Target the dialog's q-file by its
    // ``data-testid`` rather than a bare ``input[type=file]``: every
    // submodule with an ``other`` reference dataset (e.g.
    // Buildings/rooms) mounts its own hidden references file input
    // regardless of expansion state, so ``.first()`` would otherwise
    // hijack the references upload instead.
    await page
      .getByTestId('data-entry-file-input')
      .locator('input[type=file]')
      .setInputFiles({
        name: 'data.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from('header1,header2\n1,2\n', 'utf8'),
      });

    // The save button label depends on whether files are selected.
    await page.getByLabel('data-entry-save').click();

    // Both POSTs must have fired.
    await expect
      .poll(() =>
        requests.find(
          (r) =>
            r.method === 'POST' && r.url.endsWith('/api/v1/files/temp-upload'),
        ),
      )
      .toBeTruthy();

    await expect
      .poll(() =>
        requests.find(
          (r) => r.method === 'POST' && r.url.endsWith('/api/v1/sync/dispatch'),
        ),
      )
      .toBeTruthy();

    const dispatch = requests.find(
      (r) => r.method === 'POST' && r.url.endsWith('/api/v1/sync/dispatch'),
    );
    expect(dispatch?.body).toContain('"target_type":0'); // DATA_ENTRIES
    expect(dispatch?.body).toContain('"file_path":"/tmp/data.csv"');
  });

  test('5 — factors upload: same shape but target_type=FACTORS', async ({
    page,
  }) => {
    const { requests } = await mockBackend(page);
    await page.goto(DATA_MANAGEMENT_URL);

    await openHeadcountFactorsDialog(page);

    await page
      .getByTestId('data-entry-file-input')
      .locator('input[type=file]')
      .setInputFiles({
        name: 'factors.csv',
        mimeType: 'text/csv',
        buffer: Buffer.from('factor,value\nx,1\n', 'utf8'),
      });

    await page.getByLabel('data-entry-save').click();

    await expect
      .poll(() =>
        requests.find(
          (r) => r.method === 'POST' && r.url.endsWith('/api/v1/sync/dispatch'),
        ),
      )
      .toBeTruthy();

    const dispatch = requests.find(
      (r) => r.method === 'POST' && r.url.endsWith('/api/v1/sync/dispatch'),
    );
    expect(dispatch?.body).toContain('"target_type":1'); // FACTORS
  });

  test('5c — references upload: hidden file input → POST sync/dispatch with target_type=REFERENCE_DATA', async ({
    page,
  }) => {
    const { requests } = await mockBackend(page);
    await page.goto(DATA_MANAGEMENT_URL);

    // The Buildings/rooms submodule (module_type_id 3,
    // data_entry_type_id 30) ships an ``other`` reference dataset, so
    // its UploadCardReferences mounts a hidden file input even while
    // the module is collapsed.  Drive that input directly — the
    // visible "Upload Reference" button only proxies a native
    // file-picker click, a dead-end in headless Chromium.
    const refInput = page.getByTestId('reference-file-input-3-30');
    await expect(refInput).toBeAttached({ timeout: 10000 });

    await refInput.setInputFiles({
      name: 'rooms.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('room,area\nA,10\n', 'utf8'),
    });

    // References upload goes through the same temp-upload → dispatch
    // path as the dialog flow, but with TargetType.REFERENCE_DATA (3)
    // and no save-button step.
    await expect
      .poll(() =>
        requests.find(
          (r) =>
            r.method === 'POST' && r.url.endsWith('/api/v1/files/temp-upload'),
        ),
      )
      .toBeTruthy();

    await expect
      .poll(() =>
        requests.find(
          (r) => r.method === 'POST' && r.url.endsWith('/api/v1/sync/dispatch'),
        ),
      )
      .toBeTruthy();

    const dispatch = requests.find(
      (r) => r.method === 'POST' && r.url.endsWith('/api/v1/sync/dispatch'),
    );
    expect(dispatch?.body).toContain('"target_type":3'); // REFERENCE_DATA
    expect(dispatch?.body).toContain('"file_path":"/tmp/data.csv"');
  });

  test('6 — recalculate emissions: dialog → confirm → POST recalculate-emissions/{module}', async ({
    page,
  }) => {
    const { requests } = await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        // Headcount needs to be both COMPLETE and have
        // ``needs_recalculation: true`` so the recalc affordance
        // shows.  The default builder ships SUCCESS jobs; we layer
        // a ``recalculation_status`` entry on top.
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            buildYearConfig({
              year,
              recalculationStatus: [
                {
                  module_type_id: 1,
                  needs_recalculation: true,
                  data_entry_types: [
                    {
                      data_entry_type_id: 1,
                      needs_recalculation: true,
                    },
                  ],
                },
              ],
            }),
          ),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    // Wait for the year config to render so the recalc button is mounted.
    await expect(page.locator('text=/headcount/i').first()).toBeVisible();

    // Click the module-level recalc button (label depends on i18n
    // key).  It lives in the ``q-expansion-item`` header — we look
    // for the button with the ``refresh`` icon adjacent to the
    // headcount badge.
    const recalcBtn = page
      .getByRole('button', { name: /recalculate emissions/i })
      .first();
    await expect(recalcBtn).toBeVisible({ timeout: 10000 });
    await recalcBtn.click();

    // Confirm dialog.
    await page
      .getByRole('button', { name: /^confirm$/i })
      .first()
      .click();

    await expect
      .poll(() =>
        requests.find(
          (r) =>
            r.method === 'POST' &&
            /sync\/recalculate-emissions\/1(\?|$)/.test(r.url),
        ),
      )
      .toBeTruthy();
  });

  test.fixme('7 — computed factors trigger: nested SubmoduleItem button — covered by component test', async () => {
    // The ``compute-factors`` button lives 4 levels deep inside
    // ``ModuleUploadsSection > submodules slot > SubmoduleConfig
    // > SubmoduleItem > UploadCardFactors`` and is gated on
    // ``factorsOnly`` submodules with no current job.  Driving it
    // through the full Playwright tree is brittle (multiple
    // expansion clicks + dialog confirms).  Pending dedicated
    // Storybook / component-test coverage for the SubmoduleItem
    // emit chain — see Plan 310 Unit 11.
  });

  test('9 — UploadCardData renders both CSV status and API failure banner (regression)', async ({
    page,
  }) => {
    // Regression: when both latest_data_job (CSV) and latest_api_data_job
    // are returned for a submodule, the card must surface BOTH. Previously
    // a failed API ingestion was hidden because the backend preferred API
    // over CSV in _pick_latest_job — see test_failed_api_does_not_mask_
    // successful_csv on the backend side.
    const csvSuccess = {
      job_id: 100,
      module_type_id: 1,
      data_entry_type_id: 1,
      year: 2024,
      ingestion_method: 1,
      target_type: 0,
      state: 3,
      result: 0,
      status_message: 'Success',
      meta: { rows_processed: 5, file_path: '/uploads/data.csv' },
    };
    const apiFailure = {
      job_id: 200,
      module_type_id: 1,
      data_entry_type_id: 1,
      year: 2024,
      ingestion_method: 0,
      target_type: 0,
      state: 3,
      result: 2,
      status_message: 'Travel API ingestion failed',
      meta: { error: 'Centre financier missing' },
    };

    const yearConfigWithBothJobs = (year: number) => ({
      ...buildYearConfig({ year }),
      config: {
        modules: {
          '1': {
            enabled: true,
            uncertainty_tag: 'medium',
            submodules: {
              '1': {
                enabled: true,
                threshold: null,
                latest_factor_job: csvSuccess,
                latest_data_job: csvSuccess,
                latest_api_data_job: apiFailure,
              },
            },
          },
        },
        reduction_objectives: {
          files: {
            institutional_footprint: null,
            population_projections: null,
            unit_scenarios: null,
          },
          goals: [],
          institutional_footprint: [],
          population_projections: [],
          unit_scenarios: [],
        },
      },
    });

    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(yearConfigWithBothJobs(year)),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);
    await expandHeadcountAndMember(page);

    // Both statuses must coexist on the data card.
    const apiBanner = page.getByTestId('api-status-error').first();
    await expect(apiBanner).toBeVisible({ timeout: 10000 });
    await expect(apiBanner).toContainText(/Travel API ingestion failed/i);
  });

  test('9b — UploadCardData renders rows_processed for a SUCCESSFUL api job (regression)', async ({
    page,
  }) => {
    // Regression: the API success line previously read ``meta.inserted``
    // via a local ``apiRowsInserted`` computed, but the backend's API
    // ingest writes ``meta.rows_processed`` (same key as the CSV path's
    // ``getJobInfo``).  Result: the rows count was always blank on a
    // successful API ingestion.  The fix drops the local computed and
    // reuses ``apiJobInfo.rowsProcessed``; this test pins the visible
    // text so a regression re-surfaces loudly.
    const apiSuccess = {
      job_id: 300,
      module_type_id: 1,
      data_entry_type_id: 1,
      year: 2024,
      ingestion_method: 0, // API
      target_type: 0,
      state: 3,
      result: 0,
      status_message: 'Success',
      meta: { rows_processed: 10475, timestamp: '2024-01-15T00:00:00Z' },
    };

    const yearConfigApiOnly = (year: number) => ({
      ...buildYearConfig({ year }),
      config: {
        modules: {
          '1': {
            enabled: true,
            uncertainty_tag: 'medium',
            submodules: {
              '1': {
                enabled: true,
                threshold: null,
                latest_factor_job: apiSuccess,
                latest_api_data_job: apiSuccess,
              },
            },
          },
        },
        reduction_objectives: {
          files: {
            institutional_footprint: null,
            population_projections: null,
            unit_scenarios: null,
          },
          goals: [],
          institutional_footprint: [],
          population_projections: [],
          unit_scenarios: [],
        },
      },
    });

    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(yearConfigApiOnly(year)),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);
    await expandHeadcountAndMember(page);

    const apiSuccessLine = page.getByTestId('api-status-success').first();
    await expect(apiSuccessLine).toBeVisible({ timeout: 10000 });
    // The exact number must surface — proves the field-name fix
    // (meta.rows_processed, not meta.inserted) is in place.
    await expect(apiSuccessLine).toContainText(/10475/);
    await expect(apiSuccessLine).toContainText(
      /rows imported|lignes importées/i,
    );
  });

  test('8 — year-level reload-rehydrate (Issue #867): GET /sync/active-pipelines/year/{year} fires on mount and on year change', async ({
    page,
  }) => {
    // The page's empty steady-state response (``[]``) is enough — we
    // are asserting the REQUEST is fired, not the badge UI (the per-
    // pipeline UI lives further down the chain in
    // ``PipelineDiagnosticTooltip`` and is covered by its own spec).
    const { requests } = await mockBackend(page);

    await page.goto(DATA_MANAGEMENT_URL);

    // Wait for the page to finish first-render before asserting
    // request counts — the ``immediate: true`` watcher fires during
    // the synchronous setup, but the ``api.get(...).json()`` await
    // resolves a tick later.
    await expect(page.getByText(/year configuration/i).first()).toBeVisible();

    // Initial year (2024 — URL query param) must trigger one
    // year-level fetch.  Without this fetch the SSE watcher has no
    // way to discover an in-flight unit-sync after a hard reload.
    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.method === 'GET' &&
              /\/sync\/active-pipelines\/year\/2024$/.test(r.url),
          ).length,
      )
      .toBeGreaterThanOrEqual(1);

    // Change year → second fetch for the new year.  Mirrors the
    // year-config fetch pattern (test 1) but for the year-level
    // pipeline channel.
    await page.locator('.q-select').first().click();
    await page.getByRole('option', { name: '2025' }).click();

    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.method === 'GET' &&
              /\/sync\/active-pipelines\/year\/2025$/.test(r.url),
          ).length,
      )
      .toBeGreaterThanOrEqual(1);
  });
});

// ── helpers ──────────────────────────────────────────────────────────────────

/**
 * year-configuration GET handler: first call returns 404 so the
 * "Create year" card renders; subsequent calls return the standard
 * mocked config.  Used by both create-year tests.
 */
function notFoundThen200(): (route: Route, year: number) => Promise<void> {
  let calls = 0;
  return async (route, year) => {
    calls += 1;
    if (calls === 1) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'not found' }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildYearConfig({ year })),
    });
  };
}

/**
 * Expand the Headcount module card AND its ``member`` submodule, then
 * open the data-entry dialog via the ``Add Data`` / ``ReUpload Data``
 * button on the per-submodule UploadCard.
 *
 * The page nests three layers of ``q-expansion-item``:
 *   - module (Headcount)
 *   - submodule (member, student)
 *   - the upload buttons live inside the submodule body.
 */
async function openHeadcountDataDialog(page: Page): Promise<void> {
  await expandHeadcountAndMember(page);
  const dataBtn = page
    .getByRole('button', {
      name: /(re)?upload data|add data/i,
    })
    .first();
  await expect(dataBtn).toBeVisible({ timeout: 10000 });
  await dataBtn.click();
  await expect(page.getByText(/import\s+/i).first()).toBeVisible();
}

/**
 * Same shape as ``openHeadcountDataDialog`` but routes through the
 * factor card's "ReUpload Factors" / "Add Factors" button.
 */
async function openHeadcountFactorsDialog(page: Page): Promise<void> {
  await expandHeadcountAndMember(page);
  const factorBtn = page
    .getByRole('button', {
      name: /(re)?upload factors|add factors/i,
    })
    .first();
  await expect(factorBtn).toBeVisible({ timeout: 10000 });
  await factorBtn.click();
  await expect(page.getByText(/import\s+/i).first()).toBeVisible();
}

/**
 * Click through the two nested q-expansion-items needed to surface
 * the per-submodule UploadCard buttons for Headcount > member.
 *
 * Quasar's ``q-expansion-item`` renders an outer ``role=button``
 * named "Expand" that wraps the labeled content; the easiest stable
 * selector is "the Expand button containing this text".
 */
async function expandHeadcountAndMember(page: Page): Promise<void> {
  // Module-level expand button for Headcount.
  const headcountExpand = page
    .getByRole('button', { name: /expand/i })
    .filter({ hasText: /headcount/i })
    .first();
  await expect(headcountExpand).toBeVisible({ timeout: 10000 });
  await headcountExpand.click();
  // Submodule-level expand for "Member" (labelKey
  // ``headcount-member`` → "Member" singular under vue-i18n's
  // pluralization without a count argument).
  const memberExpand = page
    .getByRole('button', { name: /expand/i })
    .filter({ hasText: /member/i })
    .first();
  await expect(memberExpand).toBeVisible({ timeout: 10000 });
  await memberExpand.click();
}
/**
 * E2E coverage for the back-office "Open year for users" flow (issue #867).
 *
 * Uses the shared `installInitScripts` + `mockBackend` helpers so the
 * page renders past the auth/permission guards (Lighthouse bypass) and
 * has stubs for every endpoint the page hits on mount (auth/me,
 * active-pipelines, active-pipelines/year, year-configuration, ...).
 *
 * The button is disabled when `anyModuleIncomplete || is_started` —
 * `anyModuleIncomplete` iterates `MODULES_LIST` (8 modules) and checks
 * `isReductionObjectiveIncomplete`.  To reach the "enabled" branch we
 * mark every module disabled (so `isModuleIncomplete` short-circuits)
 * and supply a complete `reduction_objectives` (one goal + all 3 files).
 */

/** Minimal "ready to open" year config: every gate in
 *  `anyModuleIncomplete` returns false, leaving only `is_started` to
 *  drive the button's disabled state. */
function readyToOpenYearConfig(year: number, isStarted: boolean) {
  const disabledModule = {
    enabled: false,
    uncertainty_tag: 'medium',
    submodules: {},
  };
  const fileMeta = {
    path: '/uploads/x.csv',
    filename: 'x.csv',
    uploaded_at: '2024-01-01T00:00:00Z',
  };
  return {
    year,
    is_started: isStarted,
    // Year-config gate (#1234 follow-up `13616a35`): the
    // "Open year for users" button has ``v-if="!yearSyncInFlight"``,
    // and ``yearSyncInFlight`` is true while
    // ``configuration_completed == null`` (durable refresh-survival
    // signal).  These tests assume the year is fully provisioned —
    // the button should be present, just enabled/disabled depending
    // on ``is_started`` — so stamp the field.
    configuration_completed: '2024-01-01T00:00:00Z',
    config: {
      modules: {
        '1': disabledModule,
        '2': disabledModule,
        '3': disabledModule,
        '4': disabledModule,
        '5': disabledModule,
        '6': disabledModule,
        '7': disabledModule,
        '8': disabledModule,
      },
      reduction_objectives: {
        files: {
          institutional_footprint: fileMeta,
          population_projections: fileMeta,
          unit_scenarios: fileMeta,
        },
        goals: [
          { target_year: 2030, reduction_percentage: 50, reference_year: 2024 },
        ],
        institutional_footprint: [],
        population_projections: [],
        unit_scenarios: [],
      },
    },
    recalculation_status: [],
    updated_at: '2024-01-01T00:00:00Z',
  };
}

test.describe('Data management — open year for users', () => {
  test.beforeEach(async ({ context }) => {
    await installInitScripts(context);
  });

  test('button is enabled and shows success toast when year is not yet open', async ({
    page,
  }) => {
    let patchBody: unknown = null;

    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(readyToOpenYearConfig(year, false)),
        });
      },
      onUpdateYear: async (route, year) => {
        patchBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(readyToOpenYearConfig(year, true)),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    const chip = page.getByTestId('year-open-status-chip');
    await expect(chip).toContainText(/Not yet open|Pas encore ouverte/);

    const btn = page.getByTestId('open-year-for-users-btn');
    await expect(btn).toBeEnabled();
    await btn.click();

    await expect(chip).toContainText(/Open to users|Ouverte aux utilisateurs/);
    expect(patchBody).toEqual({ is_started: true });
  });

  test('button is disabled with tooltip when year is already open', async ({
    page,
  }) => {
    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(readyToOpenYearConfig(year, true)),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    const chip = page.getByTestId('year-open-status-chip');
    await expect(chip).toContainText(/Open to users|Ouverte aux utilisateurs/);

    const btn = page.getByTestId('open-year-for-users-btn');
    await expect(btn).toBeDisabled();
  });

  // Visibility-gate regressions — the button must not exist in the
  // DOM (a) before the year-configuration row is created, or (b)
  // while the unit_sync pipeline is still running.  Spec: "MUST
  // exist only once the year-configuration pipeline is fully
  // completed."
  test('button is hidden on empty-state (no year-configuration row)', async ({
    page,
  }) => {
    await mockBackend(page, {
      onGetYearConfig: async (route) => {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'not found' }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    // Empty-state card renders.
    await expect(
      page.getByRole('button', { name: /create year/i }),
    ).toBeVisible();

    // The "Open year for users" button must not exist in the DOM.
    await expect(page.getByTestId('open-year-for-users-btn')).toHaveCount(0);
  });

  test('button is hidden while the unit_sync pipeline is in flight', async ({
    page,
  }) => {
    await mockBackend(page, {
      onGetYearConfig: notFoundThen200(),
    });

    await page.goto(DATA_MANAGEMENT_URL);

    await page.getByRole('button', { name: /create year/i }).click();

    // Wait for the page to enter in-flight state (modules wrapper
    // picks up the ``inert`` attribute set by yearSyncInFlight).
    await expect(
      page.locator('div[inert].relative-position').first(),
    ).toBeVisible();

    // Mid-pipeline: button must not exist.
    await expect(page.getByTestId('open-year-for-users-btn')).toHaveCount(0);
  });
});
