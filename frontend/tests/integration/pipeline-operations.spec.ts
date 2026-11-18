/**
 * Issue #1403 slice (d) — Playwright coverage for the Pipeline
 * Operations Console (``PipelineOperationsConsolePage.vue``).
 *
 * Scope: the single #1403 checklist item this slice covers —
 * "View correctly tracks upload progress for all modules."  Reuses
 * the mocking conventions from ``pipeline-diagnostic-tooltip.spec.ts``
 * (Plan 310 / Unit 11): HTTP boundary via ``page.route``.  The page
 * polls the list endpoint while a row runs, so tests drive time with
 * ``page.clock``.
 *
 * Out of scope (see the master plan,
 * docs/src/implementation-plans/1403-backoffice-integration-tests-master.md):
 * the backend's ``compute_pipeline_progress`` phase/step computation
 * (backend-side, has its own coverage) and the recalculate-specific
 * phase-label bugs tracked by #1523/#1591 (different components).
 */

import { test, expect } from 'playwright/test';
import {
  PIPELINE_OPERATIONS_URL,
  buildPipelineItem,
  setupPipelineOperationsMocks,
  type PipelineListController,
} from './setup/pipeline-operations-mocks';

const MODULE_A_PIPELINE_ID = 'aaaaaaaa-1111-2222-3333-444444444444';
const MODULE_B_PIPELINE_ID = 'bbbbbbbb-1111-2222-3333-444444444444';

/** Mirrors ``pipeops_phase_prefix`` + ``pipeops_phase_data`` / etc. */
const PHASE_1_LABEL = 'Phase 1/3 · Data inserted';
const PHASE_2_LABEL = 'Phase 2/3 · Emissions recalculating';

test.describe('pipeline operations console — upload progress tracking (#1403d)', () => {
  let pipelines: PipelineListController;

  test.beforeEach(async ({ page }) => {
    ({ pipelines } = await setupPipelineOperationsMocks(page));
  });

  test('renders one row per active pipeline across modules', async ({
    page,
  }) => {
    pipelines.set([
      buildPipelineItem({
        pipeline_id: MODULE_A_PIPELINE_ID,
        module_type_id: 1,
        module_label: 'Headcount',
      }),
      buildPipelineItem({
        pipeline_id: MODULE_B_PIPELINE_ID,
        module_type_id: 2,
        module_label: 'Buildings',
      }),
    ]);

    await page.goto(PIPELINE_OPERATIONS_URL);

    await expect(page.getByText('Headcount', { exact: false })).toBeVisible();
    await expect(page.getByText('Buildings', { exact: false })).toBeVisible();

    // One clickable main row per pipeline — expansion detail rows
    // don't carry the ``cursor-pointer`` class, so this locator only
    // counts the top-level rows.
    await expect(page.locator('tbody tr.cursor-pointer')).toHaveCount(2);
  });

  test('progress state updates as the mocked pipeline state changes', async ({
    page,
  }) => {
    pipelines.set([
      buildPipelineItem({
        pipeline_id: MODULE_A_PIPELINE_ID,
        module_type_id: 1,
        module_label: 'Headcount',
        progress: {
          phase: 1,
          phases_total: 3,
          phase_label: 'data',
          done: false,
          has_error: false,
          status: 'RUNNING',
          kind: 'csv_ingest',
        },
      }),
    ]);

    await page.clock.install();
    await page.goto(PIPELINE_OPERATIONS_URL);
    await expect(page.getByText(PHASE_1_LABEL)).toBeVisible();

    // The page refetches the list every 5 s while a row is not done;
    // the mocked backend's new phase comes from that refetch.
    pipelines.set([
      buildPipelineItem({
        pipeline_id: MODULE_A_PIPELINE_ID,
        module_type_id: 1,
        module_label: 'Headcount',
        progress: {
          phase: 2,
          phases_total: 3,
          phase_label: 'emissions',
          done: false,
          has_error: false,
          status: 'RUNNING',
          kind: 'csv_ingest',
        },
      }),
    ]);
    await page.clock.runFor(6000);

    await expect(page.getByText(PHASE_2_LABEL)).toBeVisible();
    await expect(page.getByText(PHASE_1_LABEL)).toHaveCount(0);
  });

  test('a completed pipeline and an errored pipeline render distinctly', async ({
    page,
  }) => {
    pipelines.set([
      buildPipelineItem({
        pipeline_id: MODULE_A_PIPELINE_ID,
        module_type_id: 1,
        module_label: 'Headcount',
        status_message: 'Success',
        error_count: 0,
        progress: {
          phase: 3,
          phases_total: 3,
          phase_label: 'aggregation',
          done: true,
          has_error: false,
          status: 'SUCCESS',
          kind: 'csv_ingest',
        },
      }),
      buildPipelineItem({
        pipeline_id: MODULE_B_PIPELINE_ID,
        module_type_id: 2,
        module_label: 'Buildings',
        status_message: 'Database deadlock; retry recommended',
        error_count: 2,
        progress: {
          phase: 2,
          phases_total: 3,
          phase_label: 'emissions',
          done: true,
          has_error: true,
          status: 'FAILED',
          kind: 'csv_ingest',
        },
      }),
    ]);

    await page.goto(PIPELINE_OPERATIONS_URL);

    const doneBadge = page.locator('.q-badge', { hasText: 'Done' });
    await expect(doneBadge).toBeVisible();
    await expect(doneBadge).toHaveClass(/bg-positive/);

    const failedBadge = page.locator('.q-badge', { hasText: 'Failed' });
    await expect(failedBadge).toBeVisible();
    await expect(failedBadge).toHaveClass(/bg-negative/);

    // Error-count marker only renders on the failed row.
    await expect(page.locator('.text-negative', { hasText: '✗' })).toHaveCount(
      1,
    );
  });

  test('polls the list while a pipeline runs, with no per-pipeline stream', async ({
    page,
  }) => {
    const perPipelineUrls: string[] = [];
    page.on('request', (req) => {
      if (/\/api\/v1\/sync\/pipelines\/[^/?]+/.test(req.url())) {
        perPipelineUrls.push(req.url());
      }
    });
    pipelines.set([
      buildPipelineItem({
        pipeline_id: MODULE_A_PIPELINE_ID,
        module_label: 'Headcount',
      }),
    ]);
    await page.clock.install();
    await page.goto(PIPELINE_OPERATIONS_URL);
    await expect(page.getByText(PHASE_1_LABEL)).toBeVisible();
    const before = pipelines.requestCount();

    await page.clock.runFor(6000);

    await expect.poll(() => pipelines.requestCount()).toBeGreaterThan(before);
    expect(perPipelineUrls).toEqual([]);
    const openPipes = await page.evaluate(
      () =>
        (window as Window & { __ssePipes?: Map<string, unknown> }).__ssePipes
          ?.size ?? 0,
    );
    expect(openPipes).toBe(0);
  });

  test('does not poll when every pipeline is done', async ({ page }) => {
    pipelines.set([
      buildPipelineItem({
        pipeline_id: MODULE_A_PIPELINE_ID,
        module_label: 'Headcount',
        progress: {
          phase: 3,
          phases_total: 3,
          phase_label: 'aggregation',
          done: true,
          has_error: false,
          status: 'SUCCESS',
          kind: 'csv_ingest',
        },
      }),
    ]);
    await page.clock.install();
    await page.goto(PIPELINE_OPERATIONS_URL);
    await expect(page.locator('.q-badge', { hasText: 'Done' })).toBeVisible();
    const before = pipelines.requestCount();

    await page.clock.runFor(12000);

    expect(pipelines.requestCount()).toBe(before);
  });
});
