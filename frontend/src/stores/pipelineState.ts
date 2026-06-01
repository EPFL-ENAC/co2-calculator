/**
 * Plan 310-D / Issue #1062 — unified pipeline-state store.
 *
 * Replaces the two-store, two-endpoint coupling that previously tracked
 * the same backend state ("which pipeline is currently active for this
 * module/year?") via:
 *
 *   - ``useTimelineStore.currentPipelineIds`` keyed by ``Module`` enum,
 *     populated from ``GET /carbon-reports/{id}/modules/``
 *   - ``yearConfigStore.recalculationStatus[id].current_pipeline_id``
 *     keyed by numeric ``module_type_id``, populated from
 *     ``GET /year-configurations/{year}``
 *
 * Both views are now a single store keyed by ``(module_type_id, year)``
 * and fed by the dedicated bulk endpoint
 * ``GET /v1/sync/active-pipelines?year=Y&modules=1,2,3``.
 *
 * This store ONLY holds state.  The SSE lifecycle (``EventSource``,
 * connection refcounting, finished/error derivation) stays in
 * ``usePipelineStream`` — those are different responsibilities and
 * conflating them was part of the original bug.
 */

import { defineStore } from 'pinia';
import { reactive } from 'vue';
import { api } from 'src/api/http';

/**
 * Wire shape of ``GET /v1/sync/active-pipelines``.
 *
 * Sparse: only modules with an ACTIVE (NOT_STARTED/QUEUED/RUNNING)
 * pipeline-attached job for the requested year are present.  Modules
 * with no active pipeline are absent from the response (the steady
 * state).  Callers ``.get(...)`` and treat missing keys as "no badge".
 */
type ActivePipelinesResponse = Record<string, string>;

/**
 * Wire shape of ``GET /v1/sync/active-pipelines/year/{year}``.
 *
 * Flat list of pipeline_id UUIDs (strings) for every active
 * ``entity_type=GLOBAL_PER_YEAR`` job for the requested year.  Empty
 * list is the steady state.  Issue #867.
 */
type ActiveYearLevelPipelinesResponse = string[];

/**
 * Composite key — pipeline state is scoped to ``(module_type_id, year)``
 * because the same ``module_type_id`` can have different pipeline state
 * across years (e.g. operator looking at 2024 while a 2025 chain runs
 * in another browser tab).
 */
function makeKey(moduleTypeId: number, year: number): string {
  return `${moduleTypeId}:${year}`;
}

export const usePipelineStateStore = defineStore('pipelineState', () => {
  /**
   * Per-``(module_type_id, year)`` active pipeline_id.  ``null`` means
   * "no active pipeline" (badge clears); absence from the map means
   * "not yet loaded".
   */
  const pipelineByModuleYear = reactive<Record<string, string | null>>({});

  /**
   * Per-``year`` list of active ``GLOBAL_PER_YEAR`` pipeline_ids
   * (Issue #867).  Year-level pipelines (e.g. unit-sync) are not
   * module-scoped, so they live in a separate map keyed only on
   * ``year``.  Absence means "not yet loaded"; an empty array means
   * "loaded, no active year-level pipeline" — the steady state.
   */
  const yearLevelPipelinesByYear = reactive<Record<number, string[]>>({});

  /**
   * Bulk-fetch active pipeline_ids for the given modules in one round
   * trip.  Replaces what was previously two endpoint calls
   * (carbon-reports/modules + year-configuration) populating two
   * stores with the same value.
   *
   * Idempotent — calling twice for the same year/moduleIds simply
   * refreshes the entries.  Modules absent from the wire response
   * are explicitly stored as ``null`` so a caller can distinguish
   * "loaded, no pipeline" from "not yet loaded".
   */
  async function loadFor(year: number, moduleIds: number[]): Promise<void> {
    if (moduleIds.length === 0) return;

    const params = new URLSearchParams({
      year: String(year),
      modules: moduleIds.join(','),
    });
    const response = (await api
      .get(`sync/active-pipelines?${params.toString()}`)
      .json()) as ActivePipelinesResponse;

    for (const moduleId of moduleIds) {
      const wireKey = String(moduleId);
      pipelineByModuleYear[makeKey(moduleId, year)] = response[wireKey] ?? null;
    }
  }

  /**
   * Read the active pipeline_id for a ``(module_type_id, year)`` slice.
   * Returns ``null`` when no active pipeline exists OR when ``loadFor``
   * has never been called for this slice — both states surface as "no
   * badge", which is the desired behavior pre-load.
   */
  function getPipelineId(moduleTypeId: number, year: number): string | null {
    return pipelineByModuleYear[makeKey(moduleTypeId, year)] ?? null;
  }

  /**
   * Issue #1219 — seed a freshly-dispatched pipeline_id synchronously,
   * straight from the dispatch/recalc HTTP response, instead of waiting
   * for the next ``loadFor`` (active-pipelines) poll.  The poll only
   * runs on mount / year-change / upload-job completion, so without
   * this the card can't discover the pipeline until *after* the upload
   * job already FINISHED — phase 1 is invisible and a fast chain
   * completes inside the discovery gap.  ``ModuleConfig``'s
   * ``currentPipelineId`` computed reads this map reactively, so the
   * existing ``watch(currentPipelineId)`` auto-subscribes to the SSE
   * stream the moment this is set.
   */
  function setPipelineId(
    moduleTypeId: number,
    year: number,
    pipelineId: string,
  ): void {
    pipelineByModuleYear[makeKey(moduleTypeId, year)] = pipelineId;
  }

  /**
   * Issue #867 — bulk-fetch active year-level pipeline_ids
   * (``entity_type=GLOBAL_PER_YEAR``) for the given year.  Backs the
   * ``DataManagementPage.vue`` reload-rehydrate path: on mount + on
   * year change the page re-attaches to live year-level pipelines
   * (e.g. an in-flight unit-sync) so the SSE watcher resumes after
   * a hard reload.
   *
   * Idempotent — calling twice for the same year refreshes the list.
   * The result is the source of truth for ``getYearLevelPipelineIds``;
   * absence from the map means "not yet loaded".
   */
  async function loadYearLevelFor(year: number): Promise<void> {
    const response = (await api
      .get(`sync/active-pipelines/year/${year}`)
      .json()) as ActiveYearLevelPipelinesResponse;
    yearLevelPipelinesByYear[year] = response;
  }

  /**
   * Read the active year-level pipeline_ids for a year.  Returns an
   * empty array both pre-load and when no year-level pipeline is
   * active — the watcher in ``DataManagementPage.vue`` treats both as
   * "nothing to subscribe to" (the steady state).
   */
  function getYearLevelPipelineIds(year: number): string[] {
    return yearLevelPipelinesByYear[year] ?? [];
  }

  /**
   * Drop every entry — used when switching reports / years to ensure
   * stale ids from a previous context don't bleed through.
   */
  function clear(): void {
    for (const key of Object.keys(pipelineByModuleYear)) {
      delete pipelineByModuleYear[key];
    }
    for (const key of Object.keys(yearLevelPipelinesByYear)) {
      delete yearLevelPipelinesByYear[Number(key)];
    }
  }

  return {
    pipelineByModuleYear,
    yearLevelPipelinesByYear,
    loadFor,
    loadYearLevelFor,
    getPipelineId,
    setPipelineId,
    getYearLevelPipelineIds,
    clear,
  };
});
