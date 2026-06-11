/**
 * Pure helper: overlay the live pipeline-SSE state of a job
 * (``state`` / ``result`` / ``status_message``) onto the snapshot read
 * from ``yearConfigStore``.
 *
 * Why a dedicated file (not co-located with ``useModuleConfig``):
 * Playwright's component-test runner transpiles imports through babel
 * and chokes on Vite-only ``import.meta.glob`` inside the i18n boot
 * file, which is transitively pulled in by anything that imports a
 * Pinia store.  Keeping this helper in a leaf file with **only type
 * imports** (zero runtime store deps) means the regression test in
 * ``tests/unit/`` can import it cheaply without spinning up a full
 * Vite environment.
 *
 * Why hardcoded numeric maps for ``state`` / ``result``: the helper
 * needs to convert the SSE's enum *name* string ("RUNNING",
 * "FINISHED", "SUCCESS", …) to the snapshot's enum *value* number
 * (0, 1, 2, 3).  Importing ``IngestionState`` / ``IngestionResult``
 * for runtime access would re-introduce the runtime store dep this
 * file deliberately avoids.  The literals below MUST stay in sync
 * with the enums in ``src/stores/backofficeDataManagement.ts`` — the
 * regression test asserts the round-trip explicitly.
 */

import type { SyncJobResponse } from 'src/stores/backofficeDataManagement';
import type { PipelineJob } from 'src/stores/pipelineStream';

// Pinned to ``IngestionState`` in ``backofficeDataManagement.ts``.
const STATE_NAME_TO_VALUE: Record<string, number | undefined> = {
  NOT_STARTED: 0,
  QUEUED: 1,
  RUNNING: 2,
  FINISHED: 3,
};

// Pinned to ``IngestionResult`` in ``backofficeDataManagement.ts``.
const RESULT_NAME_TO_VALUE: Record<string, number | undefined> = {
  SUCCESS: 0,
  WARNING: 1,
  ERROR: 2,
};

/**
 * Overlay a live SSE job onto the snapshot.  Returns ``snapshot``
 * unchanged when there's no matching live entry (the steady state),
 * or a new object with ``state`` / ``result`` / ``status_message``
 * sourced from the live job and everything else (notably ``meta``,
 * which the SSE doesn't carry) kept from the snapshot.
 *
 * Pure — no Vue refs, no side effects.  See
 * ``UploadCardData.vue`` / ``UploadCardFactors.vue`` /
 * ``UploadCardReferences.vue`` for the consumer pattern.
 */
export function mergeLivePipelineJob(
  snapshot: SyncJobResponse | undefined,
  liveJobsById: ReadonlyMap<number, PipelineJob>,
): SyncJobResponse | undefined {
  if (!snapshot?.job_id) return snapshot;
  const live = liveJobsById.get(snapshot.job_id);
  if (!live) return snapshot;
  const liveState = live.state ? STATE_NAME_TO_VALUE[live.state] : undefined;
  const liveResult = live.result
    ? RESULT_NAME_TO_VALUE[live.result]
    : undefined;
  return {
    ...snapshot,
    state: (liveState ?? snapshot.state) as SyncJobResponse['state'],
    result: (liveResult ?? snapshot.result) as SyncJobResponse['result'],
    status_message: live.status_message ?? snapshot.status_message,
  };
}
