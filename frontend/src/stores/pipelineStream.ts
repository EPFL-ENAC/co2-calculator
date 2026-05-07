/**
 * Plan 310-D — pipeline-scoped SSE stream store.
 *
 * Keyed by ``pipeline_id`` so multiple module cards subscribed to the
 * same pipeline share one EventSource + one reactive entry.  The store
 * itself owns no I/O; ``usePipelineStream`` opens the EventSource and
 * pushes parsed events here via ``applyUpdate``.
 *
 * What's tracked per pipeline:
 *
 * - ``jobs``: the job snapshot from the most recent
 *   ``event: pipeline-update`` payload.  Empty list before the first
 *   event lands.
 * - ``isFinished``: derived — true when every job's state is
 *   ``FINISHED`` (or when ``stream_closed: true`` arrived).
 * - ``hasError``: derived — true when any FINISHED job has
 *   ``result === 'ERROR'``.  Drives the "Last recalc failed" badge
 *   variant in the UI.
 * - ``failedStatusMessages``: the ``status_message`` of every
 *   FINISHED+ERROR job, for the retry-button tooltip.
 * - ``subscriberCount``: refcount so ``usePipelineStream`` can decide
 *   when to actually close the EventSource (last unmount only).
 */

import { defineStore } from 'pinia';
import { computed, reactive, type ComputedRef } from 'vue';

/**
 * One job inside a pipeline-update payload.  Mirrors the backend's
 * ``PipelineJobResponse`` (Plan 310-C / PR #1052 stream endpoint).
 */
export interface PipelineJob {
  id: number;
  job_type: string | null;
  state: string | null;
  result: string | null;
  status_message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

/**
 * The wire payload of an ``event: pipeline-update`` SSE message.
 * Backend SSE endpoint: ``GET /v1/sync/pipelines/{pipeline_id}/stream``.
 */
export interface PipelineUpdate {
  pipeline_id: string;
  jobs: PipelineJob[];
  /** Terminal marker — backend sets it on the very last event. */
  stream_closed?: boolean;
}

/**
 * One-shot read response from
 * ``GET /v1/sync/pipelines/{pipeline_id}`` (Plan 310-C / PR #1023).
 * Used by ``usePipelineStream`` to seed initial state before the
 * stream takes over (mitigates the "pipeline finished between
 * carbon-report load and our subscribe" race).
 */
export interface PipelineSnapshot {
  pipeline_id: string;
  jobs: PipelineJob[];
}

interface PipelineEntry {
  jobs: PipelineJob[];
  /** ``true`` once a ``stream_closed: true`` payload has arrived. */
  closed: boolean;
  /** Refcount of mounted subscribers (composables). */
  subscriberCount: number;
}

const FINISHED = 'FINISHED';
const ERROR = 'ERROR';

export const usePipelineStreamStore = defineStore('pipelineStream', () => {
  /**
   * Per-``pipeline_id`` state.  Reactive so any subscriber can `computed()`
   * derived flags off the entry.
   */
  const entries = reactive<Record<string, PipelineEntry>>({});

  /**
   * Apply a parsed ``pipeline-update`` payload to the store.  Creates
   * the entry on first event for an unknown pipeline_id.
   */
  function applyUpdate(payload: PipelineUpdate): void {
    const entry = entries[payload.pipeline_id] ?? {
      jobs: [],
      closed: false,
      subscriberCount: 0,
    };
    entry.jobs = payload.jobs;
    if (payload.stream_closed) {
      entry.closed = true;
    }
    entries[payload.pipeline_id] = entry;
  }

  /**
   * Seed initial state from the one-shot read endpoint.  Idempotent —
   * if a stream event has already populated this entry, the seed is
   * applied as a normal update (last-write-wins on jobs).
   */
  function seedFromSnapshot(snapshot: PipelineSnapshot): void {
    applyUpdate({
      pipeline_id: snapshot.pipeline_id,
      jobs: snapshot.jobs,
    });
  }

  /**
   * Increment the refcount and return the current count.  Composables
   * call this on mount so the store can refcount across multiple
   * cards sharing the same pipeline_id.
   */
  function acquire(pipelineId: string): number {
    const entry = entries[pipelineId] ?? {
      jobs: [],
      closed: false,
      subscriberCount: 0,
    };
    entry.subscriberCount += 1;
    entries[pipelineId] = entry;
    return entry.subscriberCount;
  }

  /**
   * Decrement the refcount and return the new count.  When the count
   * hits 0, the composable can safely close the EventSource.
   * Negative results are clamped to 0 to defend against
   * unmount-without-mount sequencing edge cases.
   */
  function release(pipelineId: string): number {
    const entry = entries[pipelineId];
    if (!entry) {
      return 0;
    }
    entry.subscriberCount = Math.max(0, entry.subscriberCount - 1);
    return entry.subscriberCount;
  }

  /**
   * Drop an entry entirely.  Use sparingly — only when the consumer
   * is sure no other subscriber will need it (e.g. after the badge
   * cleared and the carbon-report response was refetched).
   */
  function clear(pipelineId: string): void {
    delete entries[pipelineId];
  }

  function jobsFor(pipelineId: string): PipelineJob[] {
    return entries[pipelineId]?.jobs ?? [];
  }

  /**
   * Reactive ``isFinished`` — true when every job in the snapshot is
   * FINISHED, OR when the stream's terminal ``stream_closed: true``
   * marker arrived.  Empty pipelines (no jobs yet) are NOT finished.
   */
  function isFinishedFor(pipelineId: string): ComputedRef<boolean> {
    return computed(() => {
      const entry = entries[pipelineId];
      if (!entry) {
        return false;
      }
      if (entry.closed) {
        return true;
      }
      if (entry.jobs.length === 0) {
        return false;
      }
      return entry.jobs.every((j) => j.state === FINISHED);
    });
  }

  /**
   * Reactive ``hasError`` — true when any FINISHED job has
   * ``result === 'ERROR'``.  The retry-button affordance is gated on
   * this flag (FINISHED+ERROR aggregation = chain stopped without
   * producing fresh stats; operator needs visible recovery).
   */
  function hasErrorFor(pipelineId: string): ComputedRef<boolean> {
    return computed(() => {
      const entry = entries[pipelineId];
      if (!entry) {
        return false;
      }
      return entry.jobs.some((j) => j.state === FINISHED && j.result === ERROR);
    });
  }

  /**
   * The ``status_message`` of every FINISHED+ERROR job in the
   * pipeline — feeds the failure-state tooltip.  Empty list when no
   * errors (the happy path).
   */
  function failedStatusMessagesFor(pipelineId: string): ComputedRef<string[]> {
    return computed(() => {
      const entry = entries[pipelineId];
      if (!entry) {
        return [];
      }
      return entry.jobs
        .filter((j) => j.state === FINISHED && j.result === ERROR)
        .map((j) => j.status_message ?? '')
        .filter((msg) => msg.length > 0);
    });
  }

  return {
    entries,
    applyUpdate,
    seedFromSnapshot,
    acquire,
    release,
    clear,
    jobsFor,
    isFinishedFor,
    hasErrorFor,
    failedStatusMessagesFor,
  };
});
