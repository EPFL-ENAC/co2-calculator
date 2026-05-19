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
 * Server-authoritative pipeline phase/done/error (Issue #1219).
 * Mirrors the backend ``PipelineProgressResponse`` /
 * ``app.services.pipeline_progress.PipelineProgress``.  The frontend
 * trusts ``done`` here instead of inferring it from a
 * possibly-incomplete job snapshot (the parent upload finishes before
 * its recalc/aggregation children are even INSERTed).
 */
export interface PipelineProgress {
  phase: number;
  phases_total: number;
  phase_label: 'data' | 'emissions' | 'aggregation';
  done: boolean;
  has_error: boolean;
}

/**
 * The wire payload of an ``event: pipeline-update`` SSE message.
 * Backend SSE endpoint: ``GET /v1/sync/pipelines/{pipeline_id}/stream``.
 */
export interface PipelineUpdate {
  pipeline_id: string;
  jobs: PipelineJob[];
  /**
   * Authoritative progress (Issue #1219).  Present on every stream
   * payload; the one-shot ``PipelineSnapshot`` seed carries it too.
   */
  progress?: PipelineProgress;
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
  progress?: PipelineProgress;
}

interface PipelineEntry {
  jobs: PipelineJob[];
  /** Latest authoritative progress, or null until the first payload. */
  progress: PipelineProgress | null;
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
   *
   * NB: ``entry.jobs = payload.jobs`` REPLACES the array reference
   * rather than mutating in place.  Vue 3's reactivity handles this
   * fine via Proxy on ``entries`` — but a future refactor that
   * destructures ``const jobs = entries[id].jobs`` once and reads
   * from the cached ref would silently lose updates.  Always re-read
   * from the store on each access (or use the ``jobsFor(id)``
   * accessor below) to avoid that footgun.
   */
  function applyUpdate(payload: PipelineUpdate): void {
    const entry = entries[payload.pipeline_id] ?? {
      jobs: [],
      progress: null,
      closed: false,
      subscriberCount: 0,
    };
    entry.jobs = payload.jobs;
    // Only overwrite progress when the payload carries it.  A
    // snapshot-only seed (legacy / transient) must not wipe an
    // authoritative progress we already received from the stream.
    if (payload.progress !== undefined) {
      entry.progress = payload.progress;
    }
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
      // Issue #1219 — forward the one-shot endpoint's authoritative
      // progress so the badge/card show the phase immediately on
      // subscribe, not only after the first ~2s SSE poll. Without
      // this the seed wipes nothing (applyUpdate skips undefined) but
      // leaves progress null until the stream catches up.
      progress: snapshot.progress,
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
      progress: null,
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
   * Reactive ``isFinished`` — Issue #1219: server-authoritative.
   * True when the backend says the *whole pipeline* is done
   * (``progress.done``), sent its terminal ``stream_closed: true``,
   * OR any job is FINISHED+ERROR.
   *
   * The old "every job in the snapshot is FINISHED" *success*
   * heuristic is deliberately gone: it fired in the window where the
   * parent upload was FINISHED but its recalc/aggregation children
   * had not been INSERTed yet, flashing the module green on a
   * half-done pipeline.
   *
   * The FINISHED+ERROR clause is kept (and matches the backend's own
   * ``done ⇔ phase3 OR any FINISHED+ERROR`` rule): a broken chain
   * spawns no further children, so an error is unambiguously terminal
   * regardless of fan-out completeness — the failure badge must show
   * even before / without an authoritative ``progress`` payload.
   */
  function isFinishedFor(pipelineId: string): ComputedRef<boolean> {
    return computed(() => {
      const entry = entries[pipelineId];
      if (!entry) {
        return false;
      }
      return (
        entry.closed ||
        entry.progress?.done === true ||
        entry.jobs.some((j) => j.state === FINISHED && j.result === ERROR)
      );
    });
  }

  /**
   * Reactive authoritative progress for the 3-phase badge, or null
   * until the first payload lands.
   */
  function progressFor(
    pipelineId: string,
  ): ComputedRef<PipelineProgress | null> {
    return computed(() => entries[pipelineId]?.progress ?? null);
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
    progressFor,
    hasErrorFor,
    failedStatusMessagesFor,
  };
});
