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
   * Drop every entry — used when switching reports / years to ensure
   * stale ids from a previous context don't bleed through.
   */
  function clear(): void {
    for (const key of Object.keys(pipelineByModuleYear)) {
      delete pipelineByModuleYear[key];
    }
  }

  return {
    pipelineByModuleYear,
    loadFor,
    getPipelineId,
    clear,
  };
});
