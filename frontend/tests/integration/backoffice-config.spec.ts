/**
 * Issue #1403 (slice c/4) — Playwright coverage for the UI-only items of
 * the BackOffice Configuration manual QA checklist: module/sub-module
 * completeness rendering, the "Ouvrir l'année pour les utilisateurs" gate,
 * uncertainty/threshold form fields, factor upload + download affordances,
 * the Incomplete tag, and step-by-step upload progress feedback.
 *
 * Reuses the ``data-management-mocks.ts`` HTTP-boundary + SSE-shim pattern
 * (``mockBackend`` / ``installInitScripts`` / ``buildYearConfig``) already
 * established by ``data-management.spec.ts`` — this file lives on the same
 * page (``DataManagementPage.vue`` IS the back-office "Configuration" tab;
 * ``requiredPermission: 'backoffice.configuration'`` in ``routes.ts``).
 *
 * What's deliberately NOT here (routed elsewhere per the #1403 master
 * plan's file split):
 *   - Config tab route access gating — extends
 *     ``tests/unit/permission.spec.ts`` (pins the
 *     ``backoffice.configuration`` + EDIT gate `permissionGuard` checks).
 *   - Backend-computed validation / status logic — that's slices a/b
 *     (``backend/tests/integration/backoffice/``).
 *   - Pipeline Operations console — ``pipeline-operations.spec.ts``
 *     (separate #1403 slice).
 */
import { test, expect, type Page } from '@playwright/test';
import {
  DATA_MANAGEMENT_URL,
  TEST_PIPELINE_ID,
  buildYearConfig,
  installInitScripts,
  mockBackend,
} from './setup/data-management-mocks';
import {
  HOME_URL,
  mockHomeBackend,
} from './setup/home-module-visibility-mocks';

// ReductionObjectivesSection renders its own "Incomplete" badge whenever
// goals/files aren't fully populated — unrelated to the module/submodule
// badges these tests target. Fully populating it isolates the assertions
// below to the module/submodule signal (mirrors the 1215b regression test
// in data-management.spec.ts).
const COMPLETE_REDUCTION_OBJECTIVES = {
  files: {
    institutional_footprint: {
      path: '/uploads/x.csv',
      filename: 'x.csv',
      uploaded_at: '2024-01-01T00:00:00Z',
    },
    population_projections: {
      path: '/uploads/x.csv',
      filename: 'x.csv',
      uploaded_at: '2024-01-01T00:00:00Z',
    },
    unit_scenarios: {
      path: '/uploads/x.csv',
      filename: 'x.csv',
      uploaded_at: '2024-01-01T00:00:00Z',
    },
  },
  goals: [
    { target_year: 2030, reduction_percentage: 50, reference_year: 2024 },
  ],
  institutional_footprint: [],
  population_projections: [],
  unit_scenarios: [],
};

test.describe('backoffice-config — module completeness at config homepage', () => {
  test.beforeEach(async ({ context }) => {
    await installInitScripts(context);
  });

  test('all 8 modules show the Incomplete label before any data is uploaded', async ({
    page,
  }) => {
    // module_type_id → module mapping per backoffice-module-config.ts:
    // 1 headcount, 2 professional-travel, 3 buildings, 4 equipment,
    // 5 purchase, 6 research-facilities, 7 external-cloud-and-ai,
    // 8 process-emissions. Every one flagged incomplete (no submodules
    // configured), mirroring the empty-state a freshly-created year is in.
    const incompleteModule = {
      enabled: true,
      uncertainty_tag: 'medium',
      incomplete: true,
      submodules: {},
    };
    const modulesOverride = Object.fromEntries(
      Array.from({ length: 8 }, (_, i) => [String(i + 1), incompleteModule]),
    );

    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...buildYearConfig({ year, modulesOverride }),
            config: {
              modules: modulesOverride,
              // ReductionObjectivesSection renders its own "Incomplete"
              // badge when unpopulated (a 9th one, unrelated to the 8
              // modules under test here) — fully populate it so the
              // count below isolates module-level badges only.
              reduction_objectives: COMPLETE_REDUCTION_OBJECTIVES,
            },
          }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    // Every module renders its own collapsed-header "Incomplete" badge —
    // no submodules are configured here, so this count is exactly the
    // module-level badges.
    await expect(page.getByText(/^incomplete$/i)).toHaveCount(8);
  });

  test('"Ouvrir l\'année pour les utilisateurs" is disabled with an informative tooltip while a module is incomplete', async ({
    page,
  }) => {
    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            buildYearConfig({
              year,
              modulesOverride: {
                '1': {
                  enabled: true,
                  uncertainty_tag: 'medium',
                  incomplete: true,
                  submodules: {},
                },
              },
            }),
          ),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    const btn = page.getByTestId('open-year-for-users-btn');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await expect(btn).toBeDisabled();

    await btn.hover();
    await expect(
      page.getByText(
        /mandatory factor and reference uploads must be completed/i,
      ),
    ).toBeVisible({ timeout: 5000 });
  });

  test('"Ouvrir l\'année pour les utilisateurs" is enabled once every module is fully loaded', async ({
    page,
  }) => {
    const completeModule = {
      enabled: true,
      uncertainty_tag: 'medium',
      incomplete: false,
      submodules: {},
    };
    const modulesOverride = Object.fromEntries(
      Array.from({ length: 8 }, (_, i) => [String(i + 1), completeModule]),
    );
    const fileMeta = {
      path: '/uploads/x.csv',
      filename: 'x.csv',
      uploaded_at: '2024-01-01T00:00:00Z',
    };

    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...buildYearConfig({ year }),
            config: {
              modules: modulesOverride,
              reduction_objectives: {
                files: {
                  institutional_footprint: fileMeta,
                  population_projections: fileMeta,
                  unit_scenarios: fileMeta,
                },
                goals: [
                  {
                    target_year: 2030,
                    reduction_percentage: 50,
                    reference_year: 2024,
                  },
                ],
                institutional_footprint: [],
                population_projections: [],
                unit_scenarios: [],
              },
            },
          }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    const btn = page.getByTestId('open-year-for-users-btn');
    await expect(btn).toBeVisible({ timeout: 10000 });
    await expect(btn).toBeEnabled();
  });
});

test.describe('backoffice-config — module & sub-module deactivation', () => {
  test.beforeEach(async ({ context }) => {
    await installInitScripts(context);
  });

  test('sub-module deactivation greys it out on the config page', async ({
    page,
  }) => {
    // Headcount's "student" submodule (data_entry_type_id 2) disabled;
    // "member" (1) stays enabled — proves the greying is per-submodule,
    // not a module-wide effect.
    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...buildYearConfig({ year }),
            config: {
              modules: {
                '1': {
                  enabled: true,
                  uncertainty_tag: 'medium',
                  incomplete: false,
                  submodules: {
                    '1': { enabled: true, threshold: null, incomplete: false },
                    '2': {
                      enabled: false,
                      threshold: null,
                      incomplete: false,
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
          }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);
    await expandModule(page, /headcount/i);

    const studentLabel = page.getByText('Student', { exact: false }).first();
    const memberLabel = page.getByText('Member', { exact: false }).first();
    await expect(studentLabel).toBeVisible({ timeout: 10000 });
    await expect(studentLabel).toHaveClass(/text-grey-6/);
    await expect(memberLabel).not.toHaveClass(/text-grey-6/);
  });
});

test.describe('backoffice-config — uncertainty & threshold fields', () => {
  test.beforeEach(async ({ context }) => {
    await installInitScripts(context);
  });

  test('uncertainty field renders the 4 correct options', async ({ page }) => {
    const { requests } = await mockBackend(page);
    await page.goto(DATA_MANAGEMENT_URL);
    await expandModule(page, /headcount/i);

    await expect(page.getByRole('radio', { name: 'None' })).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByRole('radio', { name: 'Low' })).toBeVisible();
    await expect(page.getByRole('radio', { name: 'Medium' })).toBeVisible();
    await expect(page.getByRole('radio', { name: 'High' })).toBeVisible();

    // Selecting an option persists via the same PATCH used elsewhere on
    // this page.
    await page.getByRole('radio', { name: 'Low' }).click();
    await expect
      .poll(() =>
        requests.find(
          (r) =>
            r.method === 'PATCH' &&
            /year-configuration\/2025$/.test(r.url) &&
            r.body?.includes('"uncertainty_tag":"low"'),
        ),
      )
      .toBeTruthy();
  });

  test('threshold field accepts a positive int/decimal', async ({ page }) => {
    const { requests } = await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...buildYearConfig({ year }),
            config: {
              modules: {
                // process-emissions (module_type_id 8) — unlike
                // headcount's submodules, this one does NOT set
                // ``noThreshold`` (see backoffice-module-config.ts), so
                // its threshold input actually renders.
                '8': {
                  enabled: true,
                  uncertainty_tag: 'medium',
                  incomplete: false,
                  submodules: {
                    '50': { enabled: true, threshold: null, incomplete: false },
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
          }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);

    // Every module in MODULES_LIST always renders its (static) threshold
    // UI regardless of what's configured — only the VALUES come from the
    // mock, not which modules/submodules exist in the DOM. So a page-wide
    // "Threshold" text match isn't unique; scope by module position
    // instead. MODULES_ORDER (timelineItems.ts) is
    // [headcount, process-emissions, buildings, equipment,
    // external-cloud-and-ai, professional-travel, purchase,
    // research-facilities] — process-emissions is index 1.
    await page
      .getByRole('button', { name: /expand/i })
      .nth(1)
      .click();
    // The submodule's own label is "Process Emissions" (space-separated);
    // the module's untranslated key ``process-emissions`` (hyphenated)
    // never matches this regex, so this reliably targets the submodule
    // expand button, not the module one.
    await page
      .getByRole('button', { name: /expand/i })
      .filter({ hasText: /process emissions/i })
      .click();

    // Anchor on the submodule's own label (appears exactly once) and take
    // the very next number input in document order — its own threshold
    // field, not one of the other 7 modules' (always-present) inputs.
    const submoduleLabel = page.getByText('Process Emissions', {
      exact: true,
    });
    await expect(submoduleLabel).toBeVisible({ timeout: 10000 });
    const thresholdInput = submoduleLabel.locator(
      'xpath=following::input[@type="number"][1]',
    );
    await thresholdInput.fill('12.5');
    await thresholdInput.blur();

    await expect
      .poll(() =>
        requests.find(
          (r) =>
            r.method === 'PATCH' &&
            /year-configuration\/2025$/.test(r.url) &&
            r.body?.includes('"threshold":12.5'),
        ),
      )
      .toBeTruthy();
  });

  // Issue #1403 checklist item: "Threshold field rejects negative values".
  // Traced the field (SubmoduleItem.vue's threshold `q-input`, backed by
  // useSubmoduleConfig.updateSubmoduleThreshold) — there is no `min`
  // attribute, no `:rules`, and no server-side check surfaced to the
  // frontend; typing "-5" round-trips straight into the PATCH body. This
  // is a genuine gap, not something already tracked under one of #1403's
  // sub-issues (#1204/#1415/#1433/#1463/#1491/#1523/#1545/#1558) — filing
  // a follow-up issue is out of scope for a test-only PR, so this is left
  // as an honest `fixme` rather than a test that locks in the bug or a
  // deleted assertion.
  test.fixme('threshold field rejects negative values — no client-side validation exists yet, needs a follow-up issue', () => {});
});

test.describe('backoffice-config — factor upload, download, and the Incomplete tag', () => {
  test.beforeEach(async ({ context }) => {
    await installInitScripts(context);
  });

  test('a successful factor job turns the factor box green with no error', async ({
    page,
  }) => {
    // The default builder already ships headcount/member with a SUCCESS
    // factor job — reuse it rather than re-deriving the same state.
    await mockBackend(page);
    await page.goto(DATA_MANAGEMENT_URL);
    await expandHeadcountAndMember(page);

    const factorBtn = page
      .getByRole('button', { name: /(re)?upload factors|add factors/i })
      .first();
    await expect(factorBtn).toBeVisible({ timeout: 10000 });
    await expect(factorBtn).toHaveClass(/bg-positive/);
    await expect(page.locator('.q-notification.bg-negative')).toHaveCount(0);
  });

  test('the download arrow retrieves the last uploaded factor file', async ({
    page,
  }) => {
    const processedPath = '/uploads/factors_processed.csv';
    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...buildYearConfig({ year }),
            config: {
              modules: {
                '1': {
                  enabled: true,
                  uncertainty_tag: 'medium',
                  incomplete: false,
                  submodules: {
                    '1': {
                      enabled: true,
                      threshold: null,
                      incomplete: false,
                      latest_factor_job: {
                        job_id: 1001,
                        module_type_id: 1,
                        data_entry_type_id: 1,
                        year,
                        ingestion_method: 1, // CSV — the download arrow is
                        // hidden for API-ingested jobs.
                        target_type: 1,
                        state: 3,
                        result: 0,
                        status_message: 'ok',
                        meta: {
                          rows_processed: 10,
                          processed_file_path: processedPath,
                        },
                      },
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
          }),
        });
      },
    });
    // Serve a small body so the forced-download anchor has something to
    // fetch — the ``download`` attribute on the ``<a>`` forces a Save-As
    // regardless of headers.
    await page.route(/.*\/api\/v1\/files\/.*\?d=true$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'factor,value\nx,1\n',
      }),
    );

    await page.goto(DATA_MANAGEMENT_URL);
    await expandHeadcountAndMember(page);

    const downloadBtn = page.getByTestId('download-last-csv-btn').first();
    await expect(downloadBtn).toBeVisible({ timeout: 10000 });

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      downloadBtn.click(),
    ]);
    expect(download.url()).toContain(processedPath);
  });

  test('sub-module Incomplete tag shows when the backend flags the submodule incomplete', async ({
    page,
  }) => {
    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...buildYearConfig({ year }),
            config: {
              modules: {
                '1': {
                  enabled: true,
                  uncertainty_tag: 'medium',
                  incomplete: true,
                  submodules: {
                    '1': {
                      enabled: true,
                      threshold: null,
                      incomplete: true,
                      incomplete_reasons: ['missing_factor'],
                    },
                  },
                },
              },
              reduction_objectives: COMPLETE_REDUCTION_OBJECTIVES,
            },
          }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);
    await expandModule(page, /headcount/i);

    // Module badge + submodule badge both render "Incomplete".
    await expect(page.getByText(/^incomplete$/i)).toHaveCount(2);
  });

  test('sub-module Incomplete tag clears once the backend flags it complete', async ({
    page,
  }) => {
    // Module-level incomplete stays true (a sibling submodule is still
    // missing), but THIS submodule (member, det 1) is individually
    // complete — proves the badge is submodule-scoped, not inherited from
    // the parent module (mirrors the module-level 1215b regression check
    // in data-management.spec.ts, one level down).
    await mockBackend(page, {
      onGetYearConfig: async (route, year) => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ...buildYearConfig({ year }),
            config: {
              modules: {
                '1': {
                  enabled: true,
                  uncertainty_tag: 'medium',
                  incomplete: true,
                  submodules: {
                    '1': {
                      enabled: true,
                      threshold: null,
                      incomplete: false,
                      incomplete_reasons: [],
                    },
                    '2': {
                      enabled: true,
                      threshold: null,
                      incomplete: true,
                      incomplete_reasons: ['missing_factor'],
                    },
                  },
                },
              },
              reduction_objectives: COMPLETE_REDUCTION_OBJECTIVES,
            },
          }),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);
    await expandModule(page, /headcount/i);

    // Exactly 2 badges: the module-level one (module.incomplete=true) and
    // student's (det 2) — member's (det 1) is individually complete, so
    // its badge must be absent from that count.
    await expect(page.getByText(/^incomplete$/i)).toHaveCount(2);
  });
});

test.describe('backoffice-config — upload progress feedback', () => {
  test.beforeEach(async ({ context }) => {
    await installInitScripts(context);
  });

  test('an in-flight pipeline drives step-by-step progress on the module badge', async ({
    page,
  }) => {
    await mockBackend(page, {
      onActivePipelines: async (route, moduleIds) => {
        const body: Record<string, string | null> = {};
        for (const id of moduleIds) {
          body[String(id)] = id === 1 ? TEST_PIPELINE_ID : null;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(body),
        });
      },
    });

    await page.goto(DATA_MANAGEMENT_URL);
    await expandHeadcountAndMember(page);

    // Target the per-card progress indicator (``data-testid="pipeline-phase"``
    // on ``UploadCard.vue``, which also carries the abort/"Cancel" control —
    // this is the "interactive" half of the requirement, not just static
    // text). The module-header badge shows the same phase text
    // simultaneously but isn't unique on the page (its accessible text
    // overlaps the module title), so this is the more precise target.
    const phaseIndicator = page.getByTestId('pipeline-phase');
    const cancelBtn = page.getByRole('button', { name: /cancel/i });

    const emit = (payload: unknown) =>
      page.evaluate(
        ({ id, payload: p }) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (window as any).__sse.emit(id, p);
        },
        { id: TEST_PIPELINE_ID, payload },
      );

    // Step 1/3 — data phase.
    await emit({
      pipeline_id: TEST_PIPELINE_ID,
      jobs: [
        {
          id: 1,
          job_type: 'csv_ingest',
          state: 'RUNNING',
          result: null,
          status_message: null,
          started_at: '2024-01-01T00:00:00Z',
          finished_at: null,
        },
      ],
      progress: {
        phase: 1,
        phases_total: 3,
        phase_label: 'data',
        done: false,
        has_error: false,
        kind: 'csv_ingest',
      },
      stream_closed: false,
    });
    await expect(phaseIndicator).toHaveText(/Step 1\/3 · Inserting data/, {
      timeout: 10000,
    });
    await expect(cancelBtn.first()).toBeVisible();

    await emit({
      pipeline_id: TEST_PIPELINE_ID,
      jobs: [
        {
          id: 1,
          job_type: 'csv_ingest',
          state: 'RUNNING',
          result: null,
          status_message: null,
          started_at: '2024-01-01T00:00:00Z',
          finished_at: null,
        },
      ],
      progress: {
        phase: 2,
        phases_total: 3,
        phase_label: 'emissions',
        done: false,
        has_error: false,
        kind: 'csv_ingest',
      },
      stream_closed: false,
    });
    await expect(phaseIndicator).toHaveText(
      /Step 2\/3 · Recalculating emissions/,
    );

    await emit({
      pipeline_id: TEST_PIPELINE_ID,
      jobs: [
        {
          id: 1,
          job_type: 'csv_ingest',
          state: 'RUNNING',
          result: null,
          status_message: null,
          started_at: '2024-01-01T00:00:00Z',
          finished_at: null,
        },
      ],
      progress: {
        phase: 3,
        phases_total: 3,
        phase_label: 'aggregation',
        done: false,
        has_error: false,
        kind: 'csv_ingest',
      },
      stream_closed: false,
    });
    await expect(phaseIndicator).toHaveText(/Step 3\/3 · Aggregating/);
  });
});

// ── helpers ──────────────────────────────────────────────────────────────

/** Click the module-level "Expand" button whose header text matches. */
async function expandModule(page: Page, moduleText: RegExp): Promise<void> {
  const expandBtn = page
    .getByRole('button', { name: /expand/i })
    .filter({ hasText: moduleText })
    .first();
  await expect(expandBtn).toBeVisible({ timeout: 10000 });
  await expandBtn.click();
}

/**
 * Same nested-expansion helper as ``data-management.spec.ts`` —
 * Headcount module → "Member" submodule.
 */
async function expandHeadcountAndMember(page: Page): Promise<void> {
  await expandModule(page, /headcount/i);
  const memberExpand = page
    .getByRole('button', { name: /expand/i })
    .filter({ hasText: /member/i })
    .first();
  await expect(memberExpand).toBeVisible({ timeout: 10000 });
  await memberExpand.click();
}
