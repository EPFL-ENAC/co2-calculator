/**
 * Plan 310-D — pipeline-scoped SSE consumer.
 *
 * Wraps the ``EventSource`` lifecycle for ``GET /v1/sync/pipelines/{id}/stream``
 * and pushes parsed updates into ``usePipelineStreamStore``.  The store
 * is keyed by ``pipeline_id`` so multiple module cards subscribed to
 * the same pipeline share one EventSource (refcounted via ``acquire``
 * / ``release``).
 *
 * Lifecycle the consumer needs to know:
 *
 * 1. ``subscribe(pipelineId)`` — opens the EventSource (or attaches
 *    to an existing one for the same id).  Also seeds the store from
 *    the one-shot ``GET /v1/sync/pipelines/{id}`` to mitigate the
 *    "pipeline finished between carbon-report load and our subscribe"
 *    race documented in the plan's Risks section.
 * 2. The store's reactive ``isFinishedFor(id)`` flips when the
 *    backend's terminal ``stream_closed: true`` payload arrives or
 *    every job hits FINISHED — caller can refetch the carbon report
 *    in response.
 * 3. ``unsubscribe(pipelineId)`` — decrements the refcount; the last
 *    unsubscribe closes the EventSource.
 *
 * ``onerror`` triggers exponential backoff reconnect capped at
 * ``MAX_BACKOFF_MS``; the store entry stays around so the badge
 * doesn't flicker during transient drops.
 */

import { onUnmounted } from 'vue';
import { api } from 'src/api/http';
import {
  usePipelineStreamStore,
  type PipelineSnapshot,
  type PipelineUpdate,
} from 'src/stores/pipelineStream';

/**
 * Reconnect strategy: trust native ``EventSource`` retry.
 *
 * Earlier revisions of this file shipped a custom exponential-backoff
 * reconnect loop driven by the ``onerror`` handler.  Bot review on
 * PR #1054 caught the bug: the WHATWG spec says ``onerror`` fires on
 * transient drops with ``readyState === CONNECTING`` (the browser is
 * already auto-retrying), and ``CLOSED`` is only reached after WE
 * call ``.close()``.  So our ``readyState === CLOSED`` guard never
 * fired and the documented backoff was dead code.
 *
 * Removing the dead code rather than fixing the broken state machine:
 * the browser's native retry already does what we wanted (reconnect
 * with a server-controlled or default-3s delay).  If the proxy stack
 * ever proves to mishandle that, switch back to an explicit
 * ``.close()`` + controlled reconnect — but don't ship the broken
 * variant in the meantime.
 */

interface ActiveStream {
  source: EventSource;
}

/**
 * Module-level registry so multiple composable callers (one per
 * mounted module card) share the same EventSource per pipeline_id.
 * The store's ``subscriberCount`` keeps the entry alive across
 * mount/unmount churn; the registry here owns the actual socket.
 */
const activeStreams = new Map<string, ActiveStream>();

/**
 * Optional injection point for tests — replace ``window.EventSource``
 * without touching globals.  Default is the browser's native one.
 */
type EventSourceCtor = new (url: string) => EventSource;

let eventSourceImpl: EventSourceCtor | null = null;

/** Test seam: replace the EventSource constructor used by ``subscribe``. */
export function __setEventSourceImpl(ctor: EventSourceCtor | null): void {
  eventSourceImpl = ctor;
}

function getEventSourceCtor(): EventSourceCtor {
  if (eventSourceImpl) {
    return eventSourceImpl;
  }
  return EventSource;
}

/**
 * Optional injection point for the one-shot snapshot fetch.  Default
 * uses ``fetch``; tests can swap in a stub.
 */
type SnapshotFetcher = (pipelineId: string) => Promise<PipelineSnapshot | null>;

let snapshotFetcherImpl: SnapshotFetcher | null = null;

/** Test seam: replace the snapshot fetcher used by ``subscribe``. */
export function __setSnapshotFetcher(fetcher: SnapshotFetcher | null): void {
  snapshotFetcherImpl = fetcher;
}

async function defaultSnapshotFetcher(
  pipelineId: string,
): Promise<PipelineSnapshot | null> {
  // Use the centralized ``api`` client (ky) rather than raw ``fetch``
  // so we inherit ``credentials: 'include'``, the 401-refresh-then-retry
  // hook, the 401/403 redirect-and-toast behavior, and the standardized
  // error notifications the rest of the app expects.  Bot review on
  // PR #1054 caught the bypass: a raw ``fetch`` would silently return
  // null on session expiry and we'd then open an SSE stream that
  // would also fail to authenticate.
  //
  // ``api`` has ``prefixUrl: '/api/v1/'`` configured, so the path
  // here is the suffix only.  Catch keeps the "non-fatal, fall
  // through to stream" semantics intact for transient hiccups
  // (the ``afterResponse`` hook in the api client still handles
  // 401/403 globally before we see the rejection here).
  try {
    return await api
      .get(`sync/pipelines/${pipelineId}`)
      .json<PipelineSnapshot>();
  } catch {
    // Network blip, 404 race, or post-redirect rejection — non-fatal,
    // the stream will catch up with the next ``pipeline-update`` event.
    return null;
  }
}

function getSnapshotFetcher(): SnapshotFetcher {
  return snapshotFetcherImpl ?? defaultSnapshotFetcher;
}

/**
 * Vue composable: subscribe to a pipeline_id's SSE stream and
 * automatically unsubscribe on component unmount.
 *
 * Returns ``subscribe`` / ``unsubscribe`` for callers that need to
 * switch pipeline_ids dynamically (e.g. when ``current_pipeline_id``
 * on a module card transitions ``oldId → newId``); the auto-cleanup
 * still fires on unmount for whatever the last-subscribed id was.
 */
export function usePipelineStream() {
  const store = usePipelineStreamStore();
  const ownedSubscriptions = new Set<string>();

  async function subscribe(pipelineId: string): Promise<void> {
    if (!pipelineId) {
      return;
    }
    if (ownedSubscriptions.has(pipelineId)) {
      // Same caller already subscribed — refcount is already +1
      // for this caller; treat as a no-op rather than double-counting.
      return;
    }
    ownedSubscriptions.add(pipelineId);
    store.acquire(pipelineId);

    // Seed initial state from the one-shot endpoint BEFORE the stream
    // takes over — closes the "pipeline finished between
    // carbon-report response and our subscribe" race.
    const snapshot = await getSnapshotFetcher()(pipelineId);

    // Re-check ownership after the await.  If the caller unmounted
    // during the snapshot fetch, ``onUnmounted`` already ran
    // ``unsubscribe`` (refcount → 0, but ``closeStream`` was a no-op
    // because no stream existed yet).  Without this guard we'd
    // proceed to ``openStream`` and leak an unowned EventSource.
    // Bot review on PR #1054 caught the leak.
    if (!ownedSubscriptions.has(pipelineId)) {
      return;
    }

    if (snapshot) {
      store.seedFromSnapshot(snapshot);
    }

    if (activeStreams.has(pipelineId)) {
      // Another caller already opened the EventSource for this
      // pipeline_id; we just attached the refcount above.
      return;
    }
    openStream(pipelineId);
  }

  function unsubscribe(pipelineId: string): void {
    if (!ownedSubscriptions.has(pipelineId)) {
      return;
    }
    ownedSubscriptions.delete(pipelineId);
    const remaining = store.release(pipelineId);
    if (remaining === 0) {
      closeStream(pipelineId);
    }
  }

  onUnmounted(() => {
    // Defensive cleanup — release every subscription this caller
    // holds.  Tolerates partial-mount sequences where ``subscribe``
    // was called for some ids but not others.
    for (const id of Array.from(ownedSubscriptions)) {
      unsubscribe(id);
    }
  });

  return {
    subscribe,
    unsubscribe,
    // Re-export the store's reactive accessors so callers can compute
    // badge state without a separate ``useStore()`` call.
    isFinishedFor: (id: string) => store.isFinishedFor(id),
    progressFor: (id: string) => store.progressFor(id),
    hasErrorFor: (id: string) => store.hasErrorFor(id),
    failedStatusMessagesFor: (id: string) => store.failedStatusMessagesFor(id),
    jobsFor: (id: string) => store.jobsFor(id),
  };
}

function openStream(pipelineId: string): void {
  const Ctor = getEventSourceCtor();
  const source = new Ctor(`/api/v1/sync/pipelines/${pipelineId}/stream`);
  activeStreams.set(pipelineId, { source });

  // The backend names the SSE event ``pipeline-update`` (vs the
  // default unnamed ``message``).  Listen specifically for that —
  // ``onmessage`` would only fire for unnamed events.
  source.addEventListener('pipeline-update', (raw) => {
    const event = raw as MessageEvent;
    try {
      const payload = JSON.parse(event.data) as PipelineUpdate;
      const store = usePipelineStreamStore();
      store.applyUpdate(payload);
      if (payload.stream_closed) {
        // Backend signaled end-of-stream; close the socket so the
        // browser doesn't try to reconnect via its own logic.
        closeStream(pipelineId);
      }
    } catch (err) {
      // Malformed payload — log and let the stream continue;
      // a malformed event isn't worth tearing the connection down.
      console.error('[usePipelineStream] malformed pipeline-update', err);
    }
  });

  source.addEventListener('ping', () => {
    // No-op — the heartbeat just keeps proxies awake.
  });

  // No ``onerror`` handler: native ``EventSource`` already retries
  // transient disconnects on its own clock (the browser keeps
  // ``readyState === CONNECTING`` while it does so).  The store's
  // reactive entry stays in place so the badge doesn't flicker.
  // See the "Reconnect strategy" header comment for why we
  // intentionally don't add bespoke retry logic.
}

function closeStream(pipelineId: string): void {
  const active = activeStreams.get(pipelineId);
  if (!active) {
    return;
  }
  active.source.close();
  activeStreams.delete(pipelineId);
}

/** Test-only: drop every active stream. */
export function __resetPipelineStreams(): void {
  for (const [, active] of activeStreams) {
    active.source.close();
  }
  activeStreams.clear();
}
