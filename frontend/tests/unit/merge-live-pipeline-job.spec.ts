/**
 * Regression test for ``mergeLivePipelineJob`` — the pure helper that
 * lets ``UploadCard{Data,Factors,References}`` rehydrate the per-row
 * spinner after a hard reload of the data-management page (the bug
 * Guilbert reported on 2026-05-21).
 *
 * Why this is the load-bearing test:
 *
 * - On reload, the per-job SSE opened by ``useDataEntryDialog`` is
 *   gone.  ``ModuleConfig`` still re-subscribes to the **pipeline**
 *   SSE on mount (Layer 1, drives the "Recalculating…" badge), and
 *   exposes its ``jobs[]`` payload as ``livePipelineJobsById`` via
 *   ``provide()``.
 * - The cards prefer that live state over their snapshot's
 *   ``row.last{Data,Factor,Reference}Job`` via this helper.  If the
 *   merge silently breaks (e.g. SSE enum-name → enum-value map drifts,
 *   ``meta`` accidentally clobbered), the spinner is back to frozen
 *   and the bug returns.
 *
 * The merge is a pure ``(snapshot, liveMap) → snapshot`` function — a
 * pure-function test is sufficient + the cheapest regression guard the
 * existing test infra (Playwright, no Vitest) supports.
 */

import { test, expect } from '@playwright/test';

// Import the leaf helper file directly (not via ``useModuleConfig``)
// so Playwright's babel transform doesn't follow the runtime import
// chain into the i18n boot file, which uses Vite-only
// ``import.meta.glob`` and crashes the runner.  See the head comment
// in ``mergeLivePipelineJob.ts`` for the full rationale.
import { mergeLivePipelineJob } from '../../src/composables/mergeLivePipelineJob';
// ``IngestionState`` / ``IngestionResult`` are numeric enums in
// ``backofficeDataManagement.ts``; the literals MUST match
// ``mergeLivePipelineJob``'s hardcoded lookup tables.  Re-declared
// here as type-and-value to keep the test isolated from the heavy
// store module.
const IngestionState = {
  NOT_STARTED: 0,
  QUEUED: 1,
  RUNNING: 2,
  FINISHED: 3,
} as const;
const IngestionResult = {
  SUCCESS: 0,
  WARNING: 1,
  ERROR: 2,
} as const;
const IngestionMethod = {
  API: 0,
  CSV: 1,
} as const;
const TargetType = {
  DATA_ENTRIES: 0,
} as const;

type SyncJobResponse = {
  job_id: number;
  module_type_id?: number;
  data_entry_type_id?: number;
  year?: number;
  ingestion_method: number;
  target_type?: number;
  state?: number;
  result?: number;
  status_message?: string;
  meta?: Record<string, unknown>;
};

type PipelineJob = {
  id: number;
  job_type: string | null;
  state: string | null;
  result: string | null;
  status_message: string | null;
  started_at: string | null;
  finished_at: string | null;
};

function makeSnapshot(
  overrides: Partial<SyncJobResponse> = {},
): SyncJobResponse {
  return {
    job_id: 42,
    module_type_id: 3,
    data_entry_type_id: 1,
    year: 2025,
    ingestion_method: IngestionMethod.CSV,
    target_type: TargetType.DATA_ENTRIES,
    state: IngestionState.RUNNING,
    result: IngestionResult.SUCCESS,
    status_message: 'snapshot message',
    meta: { file_name: 'headcount.csv', rows_processed: 1234 },
    ...overrides,
  };
}

function makeLiveJob(overrides: Partial<PipelineJob> = {}): PipelineJob {
  return {
    id: 42,
    job_type: 'csv_ingest',
    state: 'RUNNING',
    result: null,
    status_message: null,
    started_at: null,
    finished_at: null,
    ...overrides,
  };
}

test('returns the snapshot untouched when no matching live job exists', () => {
  const snapshot = makeSnapshot();
  const merged = mergeLivePipelineJob(snapshot, new Map());
  expect(merged).toBe(snapshot);
});

test('returns the snapshot untouched when snapshot is undefined', () => {
  const merged = mergeLivePipelineJob(
    undefined,
    new Map([[42, makeLiveJob()]]),
  );
  expect(merged).toBeUndefined();
});

test('returns the snapshot untouched when snapshot has no job_id', () => {
  // The snapshot interface allows ``job_id`` to be missing in degenerate
  // cases (e.g. empty stub rows); guard against an accidental match on
  // ``undefined`` keys.
  const snapshot = makeSnapshot({ job_id: undefined as unknown as number });
  const merged = mergeLivePipelineJob(snapshot, new Map([[42, makeLiveJob()]]));
  expect(merged).toBe(snapshot);
});

test('overlays live state when SSE reports the parent job FINISHED+SUCCESS', () => {
  // The bug: on reload, the snapshot says RUNNING and stays RUNNING
  // forever; this overlay makes the row see the live FINISHED state
  // the pipeline SSE delivered and clear the spinner.
  const snapshot = makeSnapshot({ state: IngestionState.RUNNING });
  const liveJobs = new Map<number, PipelineJob>([
    [42, makeLiveJob({ state: 'FINISHED', result: 'SUCCESS' })],
  ]);
  const merged = mergeLivePipelineJob(snapshot, liveJobs);
  expect(merged).toBeDefined();
  expect(merged?.state).toBe(IngestionState.FINISHED);
  expect(merged?.result).toBe(IngestionResult.SUCCESS);
});

test('overlays ERROR result so the failure affordance surfaces', () => {
  const snapshot = makeSnapshot({
    state: IngestionState.RUNNING,
    result: IngestionResult.SUCCESS,
  });
  const liveJobs = new Map<number, PipelineJob>([
    [
      42,
      makeLiveJob({
        state: 'FINISHED',
        result: 'ERROR',
        status_message: 'bad row 17',
      }),
    ],
  ]);
  const merged = mergeLivePipelineJob(snapshot, liveJobs);
  expect(merged?.state).toBe(IngestionState.FINISHED);
  expect(merged?.result).toBe(IngestionResult.ERROR);
  expect(merged?.status_message).toBe('bad row 17');
});

test('preserves snapshot.meta — the SSE does not carry file_name / rows_processed', () => {
  // Regression for "row shows up with no file name after reload".
  // The pipeline SSE payload is intentionally lean (no ``meta``); the
  // snapshot is the only source of the operator-visible file name and
  // row count — the overlay must not wipe it.
  const snapshot = makeSnapshot({
    meta: { file_name: 'keep-me.csv', rows_processed: 9999 },
  });
  const liveJobs = new Map<number, PipelineJob>([
    [42, makeLiveJob({ state: 'FINISHED', result: 'SUCCESS' })],
  ]);
  const merged = mergeLivePipelineJob(snapshot, liveJobs);
  expect(merged?.meta).toEqual({
    file_name: 'keep-me.csv',
    rows_processed: 9999,
  });
});

test("a different module's pipeline does not bleed into this row", () => {
  // ``ModuleConfig`` scopes ``livePipelineJobsById`` to the *current
  // module's* pipeline, but the merge helper itself doesn't know
  // about modules — it joins on ``job_id``.  Verify a non-matching
  // ``job_id`` is a no-op (defensive against a future caller passing
  // a wider map by mistake).
  const snapshot = makeSnapshot({ job_id: 42 });
  const otherPipelineJobs = new Map<number, PipelineJob>([
    [99, makeLiveJob({ id: 99, state: 'FINISHED', result: 'ERROR' })],
  ]);
  const merged = mergeLivePipelineJob(snapshot, otherPipelineJobs);
  expect(merged).toBe(snapshot);
});

test('falls back to snapshot field when SSE name is unknown', () => {
  // Defensive: if the backend ever introduces a new state name the
  // frontend hasn't been redeployed with, the row should hold its
  // snapshot value rather than going ``undefined`` (which would crash
  // ``isLoading`` downstream).
  const snapshot = makeSnapshot({ state: IngestionState.RUNNING });
  const liveJobs = new Map<number, PipelineJob>([
    [42, makeLiveJob({ state: 'NEW_FUTURE_STATE' })],
  ]);
  const merged = mergeLivePipelineJob(snapshot, liveJobs);
  expect(merged?.state).toBe(IngestionState.RUNNING);
});
