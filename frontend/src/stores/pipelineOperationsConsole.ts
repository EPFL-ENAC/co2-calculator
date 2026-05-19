/**
 * Issue #1234 — pipeline operations console store.
 *
 * Backs the back-office page that lists ingestion/recalc pipelines
 * globally (one row per ``pipeline_id``), complementary to the
 * per-module data-management page.  Thin Pinia wrapper over
 * ``GET /v1/sync/pipelines`` (paginated, filtered, meta allow-listed
 * server-side).  Drill-down/live tailing reuses the existing
 * ``usePipelineStream`` composable + ``GET /sync/pipelines/{id}`` —
 * not duplicated here.
 */

import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { api } from 'src/api/http';
import type { PipelineProgress } from 'src/stores/pipelineStream';

export interface PipelineJobListEntry {
  job_id: number;
  job_type: string | null;
  state: string | null;
  result: string | null;
  status_message: string | null;
  module_type_id: number | null;
  data_entry_type_id: number | null;
  data_entry_type_label: string | null;
  year: number | null;
  started_at: string | null;
  finished_at: string | null;
  attempts: number | null;
  meta: Record<string, unknown>;
}

export interface PipelineListItem {
  pipeline_id: string | null;
  is_orphan: boolean;
  progress: PipelineProgress;
  job_type: string | null;
  module_type_id: number | null;
  module_label: string | null;
  year: number | null;
  status_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  latest_job_id: number;
  job_count: number;
  error_count: number;
  jobs: PipelineJobListEntry[];
}

export interface PipelineListResponse {
  items: PipelineListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface PipelineFilters {
  state: string | null;
  result: string | null;
  job_type: string | null;
  year: number | null;
  has_errors: boolean | null;
  q: string;
}

const DEFAULT_FILTERS = (): PipelineFilters => ({
  state: null,
  result: null,
  job_type: null,
  year: null,
  has_errors: null,
  q: '',
});

export const usePipelineOperationsConsole = defineStore(
  'pipelineOperationsConsole',
  () => {
    const items = ref<PipelineListItem[]>([]);
    const total = ref(0);
    const limit = ref(50);
    const offset = ref(0);
    const loading = ref(false);
    const error = ref<string | null>(null);
    const filters = ref<PipelineFilters>(DEFAULT_FILTERS());

    /**
     * Alert-strip counters, derived from the current page.  Scoped to
     * the loaded page on purpose: the strip is a "what am I looking at"
     * summary, and clicking a counter sets a filter to get the true
     * server-side total for that slice.
     */
    const counters = computed(() => {
      let failed = 0;
      let errors = 0;
      let running = 0;
      let ok = 0;
      for (const p of items.value) {
        if (p.is_orphan && p.error_count > 0) failed += 1;
        if (p.error_count > 0) errors += 1;
        if (!p.progress.done) running += 1;
        else if (!p.progress.has_error) ok += 1;
      }
      return { failed, errors, running, ok };
    });

    async function fetch(): Promise<void> {
      loading.value = true;
      error.value = null;
      try {
        const params: Record<string, string> = {
          limit: String(limit.value),
          offset: String(offset.value),
        };
        const f = filters.value;
        if (f.state) params.state = f.state;
        if (f.result) params.result = f.result;
        if (f.job_type) params.job_type = f.job_type;
        if (f.year != null) params.year = String(f.year);
        if (f.has_errors != null) params.has_errors = String(f.has_errors);
        if (f.q.trim()) params.q = f.q.trim();

        const res = (await api
          .get('sync/pipelines', { searchParams: params })
          .json()) as PipelineListResponse;
        items.value = res.items;
        total.value = res.total;
      } catch (err: unknown) {
        error.value =
          err instanceof Error ? err.message : 'Failed to load pipelines';
        items.value = [];
        total.value = 0;
      } finally {
        loading.value = false;
      }
    }

    async function setPage(newOffset: number): Promise<void> {
      offset.value = Math.max(0, newOffset);
      await fetch();
    }

    async function applyFilters(
      patch: Partial<PipelineFilters>,
    ): Promise<void> {
      filters.value = { ...filters.value, ...patch };
      offset.value = 0;
      await fetch();
    }

    async function clearFilters(): Promise<void> {
      filters.value = DEFAULT_FILTERS();
      offset.value = 0;
      await fetch();
    }

    return {
      items,
      total,
      limit,
      offset,
      loading,
      error,
      filters,
      counters,
      fetch,
      setPage,
      applyFilters,
      clearFilters,
    };
  },
);
