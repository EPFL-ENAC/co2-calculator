/**
 * Plan 310 / Issue #310 — Unit 11 Playwright coverage for the bulk
 * pipeline observability surfaces shipped by PR #1059 (badge + tooltip)
 * and PR #1071 (keyboard a11y wiring).
 *
 * Boundaries:
 *
 *   - HTTP boundary is mocked via ``page.route`` (no backend dev server).
 *   - The SSE boundary is mocked via a controllable ``EventSource``
 *     shim installed BEFORE the SPA bundle boots; tests drive the
 *     stream timeline with ``page.evaluate`` calls into
 *     ``window.__ssePipes``.
 *
 * What is covered:
 *
 *   1. Badge transitions: ``null → uuid → finished`` faithfully (see
 *      the per-test comment for why the literal mid-page transition
 *      isn't testable without a user upload action).
 *   2. Tooltip content: pipeline UUID, copy-to-clipboard, per-job rows
 *      with state/result/status_message, FINISHED+ERROR rendered red.
 *   3. Keyboard a11y: focus opens / blur closes the tooltip — the
 *      F-C1 regression gate.  In-tooltip Copy button is intentionally
 *      ``test.fixme`` per the plan's Risks/Limitations section.
 *   4. SSE error path: backend 5xx on the SNAPSHOT endpoint (the only
 *      transport failure observable from the consumer — production
 *      ``usePipelineStream`` has no stream ``onerror`` handler by
 *      design) must NOT flip the badge into a permanent error state
 *      and must not spam console.error.
 */

import { test, expect, type Page } from '@playwright/test';
import {
  defaultSelectedYear,
  setupDataManagementMocks,
  mockPipelineSnapshot,
  mockPipelineStream,
  type ActivePipelinesController,
} from './setup/pipeline-tooltip-mocks';

const PIPELINE_UUID = '11111111-2222-3333-4444-555555555555';
const HEADCOUNT_MODULE_TYPE_ID = 1;
const RECALCULATING_LABEL = 'Recalculating…';
const PIPELINE_LABEL = 'Pipeline:';

/**
 * Drive an SSE event into the in-page shim.  ``url`` is the full
 * production stream URL (``/api/v1/sync/pipelines/{id}/stream``);
 * the shim looks the pipe up in ``window.__ssePipes`` and fires every
 * registered ``pipeline-update`` listener with the JSON-serialized
 * payload.
 *
 * Returns ``true`` if the pipe was found and dispatched, ``false``
 * otherwise — useful for the error-path test where we expect no pipe
 * to exist.
 */
async function dispatchPipelineUpdate(
  page: Page,
  pipelineId: string,
  payload: Record<string, unknown>,
): Promise<boolean> {
  return await page.evaluate(
    ({ pipelineId, payload }) => {
      const map = (window as Window & { __ssePipes?: Map<string, unknown> })
        .__ssePipes;
      if (!map) return false;
      const url = `/api/v1/sync/pipelines/${pipelineId}/stream`;
      const pipe = map.get(url) as
        | { dispatch(eventName: string, payload: unknown): void }
        | undefined;
      if (!pipe) return false;
      pipe.dispatch('pipeline-update', payload);
      return true;
    },
    { pipelineId, payload },
  );
}

/**
 * Wait until the in-page shim has registered an EventSource for
 * ``pipelineId``.  ``usePipelineStream.subscribe`` awaits the snapshot
 * fetch before opening the stream, so there's a non-zero gap between
 * the badge appearing and the pipe being available for ``dispatch``.
 */
async function waitForSsePipe(page: Page, pipelineId: string): Promise<void> {
  await page.waitForFunction(
    (pipelineId) => {
      const map = (window as Window & { __ssePipes?: Map<string, unknown> })
        .__ssePipes;
      if (!map) return false;
      return map.has(`/api/v1/sync/pipelines/${pipelineId}/stream`);
    },
    pipelineId,
    // Match the default expect timeout so failures surface in ~5s
    // instead of burning the full 30s test budget.
    { timeout: 5000 },
  );
}

/**
 * Navigate to the back-office data-management page with an explicit
 * year query param so tests are deterministic across calendar boundaries.
 */
async function gotoDataManagement(page: Page, year: number): Promise<void> {
  await page.goto(`/en/back-office/data-management?year=${year}`);
}

test.describe('data-management — pipeline observability + a11y (Unit 11)', () => {
  let activePipelines: ActivePipelinesController;
  const year = defaultSelectedYear();

  test.beforeEach(async ({ page, context }) => {
    // Clipboard API is gated behind permissions in chromium — tests
    // that read ``navigator.clipboard.readText`` need both grants.
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    ({ activePipelines } = await setupDataManagementMocks(page, year));
  });

  test('no badge when no active pipeline', async ({ page }) => {
    activePipelines.set({});
    await gotoDataManagement(page, year);

    // Wait for ``ModuleConfig`` to render — the "Headcount" expand-item
    // header is the earliest stable signal that the year-config
    // response landed and the v-for over ``MODULES_LIST`` ran.
    await expect(page.getByText('Headcount').first()).toBeVisible();
    await expect(page.getByText(RECALCULATING_LABEL)).toHaveCount(0);
  });

  test('badge appears when active pipeline exists, tooltip shows UUID and per-job rows', async ({
    page,
  }) => {
    activePipelines.set({ [HEADCOUNT_MODULE_TYPE_ID]: PIPELINE_UUID });
    await gotoDataManagement(page, year);

    // Badge is rendered for the headcount module.
    const badge = page.getByText(RECALCULATING_LABEL).first();
    await expect(badge).toBeVisible();

    // The SSE pipe should be opened by the composable; once it's
    // there, dispatch a representative ``pipeline-update`` so the
    // tooltip has per-job rows to show.
    await waitForSsePipe(page, PIPELINE_UUID);
    await dispatchPipelineUpdate(page, PIPELINE_UUID, {
      pipeline_id: PIPELINE_UUID,
      jobs: [
        {
          id: 1,
          job_type: 'aggregation',
          state: 'RUNNING',
          result: null,
          status_message: 'Processing batches',
          started_at: new Date(Date.now() - 5000).toISOString(),
          finished_at: null,
        },
      ],
    });

    // Hover the badge — Quasar's q-tooltip is mouse-driven.
    await badge.hover();

    // UUID renders inside the tooltip.
    await expect(page.getByText(PIPELINE_LABEL)).toBeVisible();
    await expect(
      page.locator('code').filter({ hasText: PIPELINE_UUID }),
    ).toBeVisible();

    // Per-job row: job_type · state · status_message.
    await expect(page.getByText('aggregation', { exact: false })).toBeVisible();
    await expect(page.getByText('RUNNING', { exact: false })).toBeVisible();
    await expect(page.getByText('Processing batches')).toBeVisible();
  });

  test('copy button writes pipeline UUID to clipboard', async ({ page }) => {
    activePipelines.set({ [HEADCOUNT_MODULE_TYPE_ID]: PIPELINE_UUID });
    await gotoDataManagement(page, year);

    const badge = page.getByText(RECALCULATING_LABEL).first();
    await expect(badge).toBeVisible();
    await waitForSsePipe(page, PIPELINE_UUID);
    await badge.hover();

    // The copy button is the only ``content_copy`` icon in the
    // tooltip.  Quasar's tooltip portal sets ``no-pointer-events`` on
    // the wrapper, so even ``click({ force: true })`` lands on the
    // overlay and the underlying Vue ``@click`` handler never fires.
    // Dispatch a synthetic ``click`` event straight at the button
    // element instead — the same event Vue listens for.
    const copyButton = page
      .locator('button')
      .filter({ has: page.locator('.q-icon').getByText('content_copy') })
      .first();
    await copyButton.evaluate((el) =>
      el.dispatchEvent(new MouseEvent('click', { bubbles: true })),
    );

    // Read from the deterministic clipboard mirror installed by
    // ``installPlaywrightTestShims`` — see the comment there for why
    // we can't rely on ``navigator.clipboard.readText()`` round-trips
    // in headless chromium.
    const clipboardContents = await page.evaluate(() => {
      return (
        (window as Window & { __clipboard?: { value: string } }).__clipboard
          ?.value ?? ''
      );
    });
    expect(clipboardContents).toBe(PIPELINE_UUID);
  });

  test('FINISHED + ERROR job renders red status_message', async ({ page }) => {
    activePipelines.set({ [HEADCOUNT_MODULE_TYPE_ID]: PIPELINE_UUID });
    await gotoDataManagement(page, year);

    // The SSE event flips the pipeline into the failed state.  The
    // composable's ``hasErrorFor`` returns true and the badge variant
    // becomes "Last recalc failed" (negative color).  We verify the
    // tooltip contents are rendered with the negative-color class.
    await waitForSsePipe(page, PIPELINE_UUID);
    await dispatchPipelineUpdate(page, PIPELINE_UUID, {
      pipeline_id: PIPELINE_UUID,
      jobs: [
        {
          id: 7,
          job_type: 'emission_recalc',
          state: 'FINISHED',
          result: 'ERROR',
          status_message: 'Database deadlock; retry recommended',
          started_at: new Date(Date.now() - 10000).toISOString(),
          finished_at: new Date(Date.now() - 1000).toISOString(),
        },
      ],
    });

    // Failure-state badge ("Last recalc failed") is the variant that
    // surfaces hasError=true; hover it to open its diagnostic tooltip.
    const failedBadge = page.getByText('Last recalc failed').first();
    await expect(failedBadge).toBeVisible();
    await failedBadge.hover();

    const errorMsg = page
      .getByText('Database deadlock; retry recommended')
      .first();
    await expect(errorMsg).toBeVisible();
    // Quasar's negative color resolves to the ``text-negative`` class.
    await expect(errorMsg).toHaveClass(/text-negative/);
  });

  test('badge clears after stream_closed event + active-pipelines refetch', async ({
    page,
  }) => {
    // Faithful "uuid → cleared" transition: the page loads with an
    // active pipeline (badge visible).  The SSE stream then fires its
    // terminal ``stream_closed: true`` event, which (a) sets the
    // store's ``closed`` flag → ``isFinishedFor`` flips to true → the
    // ``isRecalculating`` computed flips to false; (b) the watcher
    // refetches active-pipelines, which we flip to ``{}`` so the
    // pipelineId clears entirely.  Both effects are needed for the
    // badge to disappear in steady state — see ModuleConfig.vue's
    // post-finish watcher chain.
    activePipelines.set({ [HEADCOUNT_MODULE_TYPE_ID]: PIPELINE_UUID });
    await gotoDataManagement(page, year);

    const badge = page.getByText(RECALCULATING_LABEL).first();
    await expect(badge).toBeVisible();
    await waitForSsePipe(page, PIPELINE_UUID);

    // Flip the closure-controlled mock BEFORE dispatching the
    // terminal event; the watcher's refetch fires synchronously
    // after the SSE event.
    activePipelines.set({});

    await dispatchPipelineUpdate(page, PIPELINE_UUID, {
      pipeline_id: PIPELINE_UUID,
      jobs: [
        {
          id: 1,
          job_type: 'aggregation',
          state: 'FINISHED',
          result: 'OK',
          status_message: null,
          started_at: new Date(Date.now() - 5000).toISOString(),
          finished_at: new Date().toISOString(),
        },
      ],
      stream_closed: true,
    });

    await expect(page.getByText(RECALCULATING_LABEL)).toHaveCount(0);
  });

  test('Issue #1219: badge follows server-authoritative progress, not snapshot', async ({
    page,
  }) => {
    // Regression for the core UX bug: the parent upload job is
    // FINISHED but the pipeline as a whole is NOT — recalc/aggregation
    // children have not been INSERTed yet. The OLD "every job in the
    // snapshot is FINISHED" heuristic flashed the module green here.
    // With the authoritative ``progress`` contract the badge must stay
    // up (showing the current phase) until ``progress.done``.
    const EMISSIONS_PHASE_LABEL = 'Step 2/3 · Recalculating emissions…';

    activePipelines.set({ [HEADCOUNT_MODULE_TYPE_ID]: PIPELINE_UUID });
    await gotoDataManagement(page, year);

    const badge = page.getByText(RECALCULATING_LABEL).first();
    await expect(badge).toBeVisible();
    await waitForSsePipe(page, PIPELINE_UUID);

    // Parent FINISHED, but progress says phase 2 / not done. Badge
    // must NOT clear, and must now show the phase label.
    await dispatchPipelineUpdate(page, PIPELINE_UUID, {
      pipeline_id: PIPELINE_UUID,
      jobs: [
        {
          id: 1,
          job_type: 'csv_ingest',
          state: 'FINISHED',
          result: 'OK',
          status_message: null,
          started_at: new Date(Date.now() - 5000).toISOString(),
          finished_at: new Date().toISOString(),
        },
      ],
      progress: {
        phase: 2,
        phases_total: 3,
        phase_label: 'emissions',
        done: false,
        has_error: false,
      },
    });

    await expect(page.getByText(EMISSIONS_PHASE_LABEL)).toBeVisible();

    // Now the backend reports the whole pipeline done (no
    // stream_closed needed — ``progress.done`` is authoritative).
    activePipelines.set({});
    await dispatchPipelineUpdate(page, PIPELINE_UUID, {
      pipeline_id: PIPELINE_UUID,
      jobs: [
        {
          id: 1,
          job_type: 'csv_ingest',
          state: 'FINISHED',
          result: 'OK',
          status_message: null,
          started_at: new Date(Date.now() - 5000).toISOString(),
          finished_at: new Date().toISOString(),
        },
      ],
      progress: {
        phase: 3,
        phases_total: 3,
        phase_label: 'aggregation',
        done: true,
        has_error: false,
      },
    });

    await expect(page.getByText(EMISSIONS_PHASE_LABEL)).toHaveCount(0);
    await expect(page.getByText(RECALCULATING_LABEL)).toHaveCount(0);
  });

  test('keyboard a11y: focus opens tooltip, blur closes it (F-C1 regression gate)', async ({
    page,
  }) => {
    // Pin PR #1071 / commit b801ac56: ``q-tooltip`` is mouse-only by
    // default, so ``tabindex="0"`` alone never opens it for keyboard
    // users.  ``ModuleConfig.vue`` wires ``@focus="recalcTooltip?.show()"``
    // and ``@blur="recalcTooltip?.hide()"`` so the diagnostic content
    // is reachable without a mouse.  This test fails if that wiring
    // regresses.
    activePipelines.set({ [HEADCOUNT_MODULE_TYPE_ID]: PIPELINE_UUID });
    await gotoDataManagement(page, year);

    const badge = page.getByText(RECALCULATING_LABEL).first();
    await expect(badge).toBeVisible();
    await waitForSsePipe(page, PIPELINE_UUID);
    await dispatchPipelineUpdate(page, PIPELINE_UUID, {
      pipeline_id: PIPELINE_UUID,
      jobs: [
        {
          id: 1,
          job_type: 'aggregation',
          state: 'RUNNING',
          result: null,
          status_message: 'Processing',
          started_at: new Date().toISOString(),
          finished_at: null,
        },
      ],
    });

    // Programmatic focus mirrors what Tab navigation does for
    // ``tabindex="0"`` elements without the noise of relying on the
    // browser's tab-order calculus over a deeply-nested page.
    await badge.focus();

    // Tooltip opens — ``Pipeline:`` label is exclusive to the
    // diagnostic tooltip body.
    await expect(page.getByText(PIPELINE_LABEL)).toBeVisible();

    // Blur — Quasar's ``q-tooltip`` removes itself from the DOM on
    // ``hide``, so the assertion is "no Pipeline: anywhere".
    await badge.blur();
    await expect(page.getByText(PIPELINE_LABEL)).toHaveCount(0);
  });

  // Documented limitation from PR #1071: the in-tooltip Copy button is
  // not keyboard-reachable today because tabbing into it blurs the
  // anchor badge and Quasar's ``<q-tooltip>`` portal collapses on
  // anchor blur.  Full keyboard reachability requires switching the
  // primitive (``<q-popup-proxy>`` / ``<q-menu>``) — tracked in the
  // 310-D plan's Limitations section.  Marking ``test.fixme`` so this
  // shows up in the report as known-not-implemented rather than a
  // silent gap.
  test.fixme('keyboard a11y: copy-pipeline-id button is reachable via Tab (known limitation)', async () => {
    // Intentionally empty — see comment above and
    // docs/src/implementation-plans/310-d-frontend-stale-stats.md
    // (Click-to-stick / full keyboard reachability follow-up).
  });

  test('snapshot 5xx does not turn badge into a permanent error', async ({
    page,
  }) => {
    // Production ``usePipelineStream`` has no ``onerror`` handler by
    // design (see the file's "Reconnect strategy" header comment —
    // native ``EventSource`` retries transient drops on its own
    // clock).  So a stream-endpoint 5xx is structurally unobservable
    // from the consumer side: this test exercises the SNAPSHOT 5xx
    // path (``GET /api/v1/sync/pipelines/{id}``, the one-shot fetch
    // ``subscribe`` does before opening the stream).  The composable's
    // ``defaultSnapshotFetcher`` swallows the rejection and falls
    // through to ``openStream``; the badge should stay in the
    // "Recalculating…" state (not flip to a failure variant) and the
    // page should not emit unhandled console errors.

    // Tear down the default mocks for the two stream-related routes
    // and re-register them with 5xx behaviour.  Playwright matches
    // last-registered first, so the new handlers win without
    // disturbing the catch-all from beforeEach.
    await page.unroute(/\/api\/v1\/sync\/pipelines\/[^/]+$/);
    await page.unroute(/\/api\/v1\/sync\/pipelines\/[^/]+\/stream$/);
    await mockPipelineSnapshot(page, { status: 502 });
    await mockPipelineStream(page, { status: 502 });

    // Track console.error: error path should be silent (composable's
    // catch-and-fall-through behaviour means no thrown rejection
    // bubbles up).  ``[usePipelineStream] malformed pipeline-update``
    // is the only allow-listed source from the production code, but
    // we don't dispatch malformed events here.
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    activePipelines.set({ [HEADCOUNT_MODULE_TYPE_ID]: PIPELINE_UUID });
    await gotoDataManagement(page, year);

    const badge = page.getByText(RECALCULATING_LABEL).first();
    await expect(badge).toBeVisible();

    // The badge still says "Recalculating…" (info color) — it has not
    // flipped to "Last recalc failed" because the store has no
    // FINISHED+ERROR jobs.  The ``hasErrorFor`` computed only flips
    // on actual job state, not on transport-level failures.
    await expect(page.getByText('Last recalc failed')).toHaveCount(0);

    // No console spam from the snapshot 5xx — the composable
    // intentionally swallows the rejection.
    expect(
      consoleErrors.filter((msg) => msg.includes('[usePipelineStream]')),
    ).toEqual([]);
  });
});
