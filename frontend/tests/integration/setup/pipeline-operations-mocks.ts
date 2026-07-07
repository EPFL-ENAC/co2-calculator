/**
 * Issue #1403 slice (d) — HTTP-boundary mocks for the pipeline
 * operations console Playwright spec.
 *
 * Reuses the SSE/EventSource shim and the per-pipeline snapshot +
 * stream route mocks from ``pipeline-tooltip-mocks.ts`` (Plan 310 /
 * Unit 11) rather than reinventing them — the console page subscribes
 * through the exact same ``usePipelineStream`` composable the
 * data-management page uses.  This file only adds what's specific to
 * ``PipelineOperationsConsolePage``: the list endpoint
 * (``GET /v1/sync/pipelines``) and the workers panel
 * (``GET /v1/sync/workers``).
 */

import type { Page } from '@playwright/test';
import type {
  PipelineListItem,
  PipelineListResponse,
} from 'src/stores/pipelineOperationsConsole';
import {
  installPlaywrightTestShims,
  mockApiCatchAll,
  mockPipelineSnapshot,
  mockPipelineStream,
} from './pipeline-tooltip-mocks';

export const PIPELINE_OPERATIONS_URL = '/en/back-office/pipeline-operations';

/**
 * Closure-controlled wrapper around the list route handler — tests
 * flip the returned items mid-flow (e.g. simulate the debounced
 * refetch triggered by an SSE update returning an updated phase).
 */
export interface PipelineListController {
  set(items: PipelineListItem[]): void;
}

/**
 * Register a closure-controlled mock for ``GET /api/v1/sync/pipelines``
 * (the paginated list — NOT the per-id snapshot/stream, which are
 * distinct path shapes matched by the regexes in
 * ``pipeline-tooltip-mocks.ts``).
 */
export async function mockPipelineList(
  page: Page,
): Promise<PipelineListController> {
  let current: PipelineListItem[] = [];
  await page.route(
    /\/api\/v1\/sync\/pipelines(\?[^/]*)?$/,
    async (route) => {
      const body: PipelineListResponse = {
        items: current,
        total: current.length,
        limit: 50,
        offset: 0,
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(body),
      });
    },
  );
  return {
    set(items) {
      current = items;
    },
  };
}

/**
 * Workers panel is independent of the pipeline-progress behavior this
 * spec targets — stub it to an empty list so ``hasMultipleGitShas``
 * (a plain ``.map`` over the array) doesn't throw on mount.
 */
export async function mockWorkers(page: Page): Promise<void> {
  await page.route('**/api/v1/sync/workers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]',
    });
  });
}

/**
 * Wire every mock the console page needs in one call.  Registration
 * order matches ``setupDataManagementMocks``: most-general
 * (catch-all) first, specific routes layered after so they win
 * (Playwright matches last-registered first).
 */
export async function setupPipelineOperationsMocks(
  page: Page,
): Promise<{ pipelines: PipelineListController }> {
  await installPlaywrightTestShims(page);
  await mockApiCatchAll(page);
  await mockWorkers(page);
  const pipelines = await mockPipelineList(page);
  await mockPipelineSnapshot(page);
  await mockPipelineStream(page);
  return { pipelines };
}

/**
 * Build one ``PipelineListItem`` fixture with sensible defaults —
 * tests override only the fields they care about.
 */
export function buildPipelineItem(
  overrides: Partial<PipelineListItem> & { pipeline_id: string },
): PipelineListItem {
  const defaultProgress: PipelineListItem['progress'] = {
    phase: 1,
    phases_total: 3,
    phase_label: 'data',
    done: false,
    has_error: false,
    status: 'RUNNING',
    kind: 'csv_ingest',
  };
  return {
    is_orphan: false,
    job_type: 'csv_ingest',
    entity_type: 'MODULE_PER_YEAR',
    unit_institutional_id: null,
    module_type_id: 1,
    module_label: 'Headcount',
    year: 2025,
    status_message: null,
    author: 'test@example.com',
    started_at: new Date(Date.now() - 5000).toISOString(),
    finished_at: null,
    latest_job_id: 1,
    job_count: 1,
    error_count: 0,
    jobs: [],
    ...overrides,
    progress: { ...defaultProgress, ...overrides.progress },
  };
}
