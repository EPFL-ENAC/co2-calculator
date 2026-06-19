<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { copyToClipboard, debounce, Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import { api } from 'src/api/http';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import { usePipelineStream } from 'src/composables/usePipelineStream';
import { usePipelineStreamStore } from 'src/stores/pipelineStream';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';
import {
  usePipelineOperationsConsole,
  type PipelineListItem,
  type PipelineJobListEntry,
} from 'src/stores/pipelineOperationsConsole';

/**
 * Wire shape of ``GET /v1/sync/workers`` — one row per live pod.
 * Surfaces git_sha + claimed-jobs count so an operator can spot
 * a two-pods-on-different-code conflict at a glance (the
 * local+stage scenario from 2026-05-21).
 */
interface WorkerRow {
  pod_id: string;
  git_sha: string | null;
  app_version: string | null;
  started_at: string;
  last_heartbeat_at: string;
  heartbeat_age_seconds: number;
  claimed_job_count: number;
}

const { t } = useI18n();

const store = usePipelineOperationsConsole();
const backofficeStore = useBackofficeDataManagement();

// Abort dialog — one-step confirmation so an accidental click on a
// row doesn't kill a long-running chain mid-flight.  Mirrors the
// data-management abort flow (which doesn't confirm because it's
// scoped to a single visible card; on the ops page an operator
// may be looking at a list and click the wrong row).
const abortDialog = ref(false);
const abortTarget = ref<PipelineListItem | null>(null);
const aborting = ref(false);

function openAbortDialog(p: PipelineListItem): void {
  abortTarget.value = p;
  abortDialog.value = true;
}

async function confirmAbort(): Promise<void> {
  const target = abortTarget.value;
  if (!target?.pipeline_id) return;
  aborting.value = true;
  try {
    await backofficeStore.abortPipeline(target.pipeline_id);
    Notify.create({
      type: 'positive',
      message: t('pipeops_abort_success'),
      timeout: 1800,
    });
    abortDialog.value = false;
    abortTarget.value = null;
    // Re-fetch immediately so the row reflects FAILED status without
    // waiting for the SSE refresh — the abort wrote terminal state
    // server-side and the SSE will deliver the same eventually, but
    // an explicit refetch makes the UI feel decisive.
    await store.fetch();
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : t('pipeops_abort_failed');
    Notify.create({ type: 'negative', message: msg });
  } finally {
    aborting.value = false;
  }
}

// Processed-CSV download — surfaces ``meta.processed_file_path``
// straight from the pipeline row so an operator triaging a stalled
// or failed chain can grab the source CSV in one click.  Mirrors
// the data-management ``downloadLastCsv`` flow:
//
// * ``?d=true`` flips the backend into download mode (sets
//   ``Content-Disposition: attachment; filename="…"`` so Safari /
//   Chrome both save with the original extension — see
//   ``backend/app/api/v1/files.py``).
// * ``a.download`` is a belt-and-braces fallback for older browsers.
function processedCsvJob(p: PipelineListItem): PipelineJobListEntry | null {
  // Pick the FIRST job in id order that carries a processed_file_path.
  // For a typical chain that's the parent csv_ingest / factor_ingest
  // / reference_ingest — the operator's actual source CSV.  Downstream
  // ``emission_recalc`` / ``aggregation`` rows don't stage CSVs, so
  // they're naturally skipped.
  for (const j of p.jobs) {
    const path = (j.meta as Record<string, unknown> | undefined)
      ?.processed_file_path;
    if (typeof path === 'string' && path.length > 0) return j;
  }
  return null;
}

function downloadProcessedCsv(p: PipelineListItem): void {
  const j = processedCsvJob(p);
  if (!j) return;
  const filePath = (j.meta as Record<string, unknown>)
    .processed_file_path as string;
  const a = document.createElement('a');
  a.href = `/api/v1/files/${filePath}?d=true`;
  a.download = filePath.split('/').pop() || filePath;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

const expanded = ref<Set<string>>(new Set());

// UI1 — full-message dialog + copy-to-clipboard.
const msgDialog = ref(false);
const msgText = ref('');

function openMsg(text: string | null): void {
  if (!text) return;
  msgText.value = text;
  msgDialog.value = true;
}

async function copyMsg(): Promise<void> {
  try {
    await copyToClipboard(msgText.value);
    Notify.create({ type: 'positive', message: 'Copied', timeout: 1200 });
  } catch {
    Notify.create({ type: 'negative', message: 'Copy failed' });
  }
}

function rowKey(p: PipelineListItem): string {
  return p.pipeline_id ?? `orphan-${p.latest_job_id}`;
}

function toggle(p: PipelineListItem): void {
  const k = rowKey(p);
  if (expanded.value.has(k)) expanded.value.delete(k);
  else expanded.value.add(k);
  // reassign so the template recomputes
  expanded.value = new Set(expanded.value);
}

type StatusKind = 'failed' | 'partial' | 'running' | 'warning' | 'done';

function hasWarning(p: PipelineListItem): boolean {
  return p.jobs.some((j) => j.state === 'FINISHED' && j.result === 'WARNING');
}

// PARTIAL tier (#1236) — when the root ingest succeeded (data landed)
// but a downstream child errored, the backend writes
// ``pipelines.status = PARTIAL``.  Render it as amber, not red:
// FAILED is "data didn't land", PARTIAL is "data landed, chain had
// issues" — different operator action.  Falls back to has_error/done
// for orphans whose Pipeline row was never minted (progress.status
// is null).
function statusOf(p: PipelineListItem): StatusKind {
  if (p.progress.status === 'PARTIAL') return 'partial';
  if (p.progress.status === 'FAILED') return 'failed';
  if (p.progress.has_error) return 'failed'; // orphan / legacy fallback
  if (!p.progress.done) return 'running';
  if (hasWarning(p)) return 'warning';
  return 'done';
}

const STATUS_META: Record<
  StatusKind,
  { color: string; icon: string; key: string }
> = {
  failed: { color: 'negative', icon: 'error', key: 'pipeops_status_failed' },
  // PARTIAL shares the amber color with WARNING (both mean "needs
  // attention, not catastrophic") but uses a distinct icon + label
  // so the operator can tell the two apart at a glance.
  partial: {
    color: 'warning',
    icon: 'report_problem',
    key: 'pipeops_status_partial',
  },
  running: { color: 'primary', icon: 'sync', key: 'pipeops_status_running' },
  warning: { color: 'warning', icon: 'warning', key: 'pipeops_status_warning' },
  done: { color: 'positive', icon: 'check_circle', key: 'pipeops_status_done' },
};

function jobColor(j: { state: string | null; result: string | null }): string {
  if (j.state !== 'FINISHED') return 'grey';
  if (j.result === 'ERROR') return 'negative';
  if (j.result === 'WARNING') return 'warning';
  return 'positive';
}

/**
 * Count of jobs in FINISHED state — the right denominator for the
 * "X/N ✓" column.  ``job_count`` is the total; ``finished`` is how
 * many are actually done (FINISHED state regardless of result).
 */
function jobsFinishedCount(p: PipelineListItem): number {
  return p.jobs.filter((j) => j.state === 'FINISHED').length;
}

/**
 * Pipeline-level message for the "Message" column — replaces the
 * root job's ``status_message`` which was misleading while the chain
 * was still running ("Success" displayed even though
 * emission_recalc / aggregation children were RUNNING).
 *
 * Rules:
 * - Pipeline DONE (success/partial/failed): show the root's
 *   status_message verbatim (carries the cause for errors via the
 *   #1219 ``finalize_ingest_meta`` enrichment).
 * - Pipeline RUNNING and progress carries a phase: show
 *   ``Phase {n}/3 · {phase_label}`` (the same phrasing the
 *   data-management page uses, just inline).
 * - Otherwise: dash.
 */
function pipelineMessage(p: PipelineListItem): string | null {
  if (p.progress.done) return p.status_message ?? null;
  if (p.progress.phase && p.progress.phase_label) {
    const phaseI18n: Record<string, string> = {
      data: 'pipeops_phase_data',
      emissions: 'pipeops_phase_emissions',
      aggregation: 'pipeops_phase_aggregation',
    };
    const key = phaseI18n[p.progress.phase_label];
    const label = key ? t(key) : p.progress.phase_label;
    return `${t('pipeops_phase_prefix')} ${p.progress.phase}/${p.progress.phases_total} · ${label}`;
  }
  return null;
}

function fmtDuration(a: string | null, b: string | null): string {
  if (!a) return '—';
  const start = new Date(a).getTime();
  const end = b ? new Date(b).getTime() : Date.now();
  const ms = Math.max(0, end - start);
  // Sub-second jobs render "<1s" instead of "0s" — common for the
  // trailing aggregation after 4A.3 scoped the write set down to just
  // the affected modules.  "0s" read as "didn't run"; "<1s" says
  // "ran, was just fast".
  if (ms < 1000) return ms === 0 && !b ? '—' : '<1s';
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m${String(s % 60).padStart(2, '0')}s`;
  return `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}m`;
}

function fmtWhen(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleString();
}

// Scope label for the "Type" column.  Backend sends the entity_type
// enum NAME; unit-specific runs also carry the unit's institutional_id,
// appended so an operator sees *which* unit at a glance.
const ENTITY_TYPE_KEY: Record<string, string> = {
  MODULE_PER_YEAR: 'pipeops_type_per_year',
  MODULE_UNIT_SPECIFIC: 'pipeops_type_unit_specific',
  GLOBAL_PER_YEAR: 'pipeops_type_global',
};

function typeLabel(p: PipelineListItem): string {
  if (!p.entity_type) return '—';
  const key = ENTITY_TYPE_KEY[p.entity_type];
  const label = key ? t(key) : p.entity_type;
  if (p.entity_type === 'MODULE_UNIT_SPECIFIC' && p.unit_institutional_id) {
    return `${label} · ${p.unit_institutional_id}`;
  }
  return label;
}

const counters = computed(() => store.counters);

// Workers section — independent from the pipelines table.  Refreshed
// on mount, on user click, and on every pipelines-table refresh so
// the two views stay in sync when an operator chases a pod conflict.
// Not SSE-driven because pod heartbeats are slow-moving (~30s) and a
// dedicated stream would add no value over plain refetch.
const workers = ref<WorkerRow[]>([]);
const workersLoading = ref(false);
const workersError = ref<string | null>(null);

async function fetchWorkers(): Promise<void> {
  workersLoading.value = true;
  workersError.value = null;
  try {
    workers.value = (await api.get('sync/workers').json()) as WorkerRow[];
  } catch (err: unknown) {
    workersError.value =
      err instanceof Error ? err.message : 'Failed to load workers';
    workers.value = [];
  } finally {
    workersLoading.value = false;
  }
}

// "Two pods on different revisions" is the load-bearing signal the
// workers view exists to surface (motivating 2026-05-21 incident).
// Compute once over the loaded set so the template can render a
// banner above the table.
const hasMultipleGitShas = computed<boolean>(() => {
  const shas = new Set(
    workers.value
      .map((w) => w.git_sha)
      .filter((s): s is string => typeof s === 'string' && s.length > 0),
  );
  return shas.size > 1;
});

function shortSha(sha: string | null): string {
  if (!sha) return '—';
  return sha.length > 7 ? sha.slice(0, 7) : sha;
}

function fmtHeartbeatAge(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h`;
}

// #1236 Phase 3 read-flip: ``state`` is the pipeline-level
// ``pipelines.status`` (server-authoritative), not the job-level state.
// The 5 values match the backend ``PipelineStatus`` enum.
const stateOptions = ['NOT_STARTED', 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED'];
const jobTypeOptions = [
  'csv_ingest',
  'factor_ingest',
  'api_ingest',
  'emission_recalc',
  'aggregation',
  'unit_sync',
];

// #2D — phase checklist + status_history rendering
interface PhaseEntry {
  name: string;
  state: string;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
}
interface HistoryEntry {
  message: string;
  ts: string;
}

function jobPhases(j: { meta: Record<string, unknown> }): PhaseEntry[] {
  const raw = j.meta?.phases;
  return Array.isArray(raw) ? (raw as PhaseEntry[]) : [];
}

function jobHistory(j: { meta: Record<string, unknown> }): HistoryEntry[] {
  const raw = j.meta?.status_history;
  return Array.isArray(raw) ? (raw as HistoryEntry[]) : [];
}

function phaseColor(p: PhaseEntry): string {
  if (p.state === 'finished') return 'positive';
  if (p.state === 'running') return 'primary';
  if (p.state === 'failed' || p.error) return 'negative';
  return 'grey';
}

function phaseIcon(p: PhaseEntry): string {
  if (p.state === 'finished') return 'check_circle';
  if (p.state === 'running') return 'sync';
  if (p.state === 'failed' || p.error) return 'error';
  return 'radio_button_unchecked';
}

function fmtTs(s: string | null | undefined): string {
  if (!s) return '—';
  const d = new Date(s);
  return d.toLocaleTimeString();
}

onMounted(() => {
  void store.fetch();
  void fetchWorkers();
});

// 🐞#3 (Guilbert 2026-05-20) — SSE live-update on the ops page.
//
// Strategy: subscribe to every visible RUNNING pipeline's SSE stream;
// on any update, the canonical list endpoint is the source of truth so
// we refetch (debounced) and the table re-renders. This keeps state
// consistent (jobs, counts, status_message) without per-cell merging.
const { subscribe, unsubscribe } = usePipelineStream();
const pipelineStreamStore = usePipelineStreamStore();
const subscribedIds = new Set<string>();

const debouncedRefetch = debounce(() => {
  void store.fetch();
}, 500);

function syncSubscriptions(): void {
  // Desired set: visible pipelines that are NOT done and have a real
  // pipeline_id (orphans have none — nothing to subscribe to).
  const desired = new Set<string>();
  for (const p of store.items) {
    if (p.pipeline_id && !p.progress.done) {
      desired.add(p.pipeline_id);
    }
  }
  // Subscribe newcomers.
  for (const id of desired) {
    if (!subscribedIds.has(id)) {
      void subscribe(id);
      subscribedIds.add(id);
    }
  }
  // Unsubscribe pipelines that left the page or finished.
  for (const id of [...subscribedIds]) {
    if (!desired.has(id)) {
      unsubscribe(id);
      subscribedIds.delete(id);
    }
  }
}

watch(() => store.items, syncSubscriptions, { deep: false });

// Any SSE update for any subscribed pipeline → refetch the list
// (debounced so a burst of child terminals doesn't thrash the API).
watch(() => pipelineStreamStore.entries, debouncedRefetch, { deep: true });

onUnmounted(() => {
  for (const id of subscribedIds) unsubscribe(id);
  subscribedIds.clear();
});
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_PIPELINE_OPERATIONS" />
    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <div class="text-body1 q-mb-lg">{{ $t('pipeops_subtitle') }}</div>

        <!-- Workers panel — surfaces "who's actually polling jobs right
             now" so an operator can spot a two-pods-on-different-code
             conflict immediately.  The 2026-05-21 stuck-recalc came
             down to a dev branch running locally against the stage DB
             while the deployed stage app was ALSO running; logs gave
             no signal that two pods were active. -->
        <q-card flat bordered class="q-mb-lg">
          <q-card-section class="row items-center q-py-sm">
            <div class="text-subtitle2 q-mr-md">
              {{ $t('pipeops_workers_title') }}
            </div>
            <q-badge color="grey-7" text-color="white">
              {{ workers.length }} {{ $t('pipeops_workers_count_suffix') }}
            </q-badge>
            <q-space />
            <q-btn
              flat
              dense
              icon="refresh"
              :loading="workersLoading"
              @click="fetchWorkers"
            >
              <q-tooltip>{{ $t('pipeops_refresh') }}</q-tooltip>
            </q-btn>
          </q-card-section>
          <q-banner
            v-if="hasMultipleGitShas"
            class="bg-warning text-white q-mx-md q-mb-sm rounded-borders"
            dense
          >
            <q-icon name="report_problem" class="q-mr-xs" />
            {{ $t('pipeops_workers_multi_sha_warning') }}
          </q-banner>
          <q-banner
            v-if="workersError"
            class="bg-negative text-white q-mx-md q-mb-sm rounded-borders"
            dense
          >
            {{ workersError }}
          </q-banner>
          <q-markup-table
            v-if="workers.length"
            flat
            dense
            separator="horizontal"
          >
            <thead>
              <tr>
                <th class="text-left">{{ $t('pipeops_workers_col_pod') }}</th>
                <th class="text-left">{{ $t('pipeops_workers_col_sha') }}</th>
                <th class="text-left">
                  {{ $t('pipeops_workers_col_version') }}
                </th>
                <th class="text-left">
                  {{ $t('pipeops_workers_col_heartbeat') }}
                </th>
                <th class="text-right">
                  {{ $t('pipeops_workers_col_jobs') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="w in workers" :key="w.pod_id">
                <td class="text-monospace">{{ w.pod_id }}</td>
                <td class="text-monospace">{{ shortSha(w.git_sha) }}</td>
                <td>{{ w.app_version ?? '—' }}</td>
                <td>
                  {{ fmtHeartbeatAge(w.heartbeat_age_seconds) }}
                  <span class="text-caption text-grey-6">
                    {{ $t('pipeops_workers_ago') }}
                  </span>
                </td>
                <td class="text-right">
                  <q-badge
                    :color="w.claimed_job_count > 0 ? 'primary' : 'grey-5'"
                    text-color="white"
                  >
                    {{ w.claimed_job_count }}
                  </q-badge>
                </td>
              </tr>
            </tbody>
          </q-markup-table>
          <q-card-section
            v-else-if="!workersLoading"
            class="text-center text-grey-7 q-py-md"
          >
            {{ $t('pipeops_workers_empty') }}
          </q-card-section>
        </q-card>

        <!-- Alert strip — clickable counters set a filter -->
        <div class="row q-col-gutter-md q-mb-lg">
          <div class="col-auto">
            <q-chip
              clickable
              color="negative"
              text-color="white"
              icon="error"
              @click="store.applyFilters({ has_errors: true })"
            >
              {{ counters.errors }} · {{ $t('pipeops_alert_errors') }}
            </q-chip>
          </div>
          <div class="col-auto">
            <q-chip
              clickable
              color="primary"
              text-color="white"
              icon="sync"
              @click="store.applyFilters({ state: 'RUNNING' })"
            >
              {{ counters.running }} · {{ $t('pipeops_alert_running') }}
            </q-chip>
          </div>
          <div class="col-auto">
            <q-chip color="positive" text-color="white" icon="check_circle">
              {{ counters.ok }} · {{ $t('pipeops_alert_ok') }}
            </q-chip>
          </div>
          <div class="col-auto">
            <q-chip color="grey-7" text-color="white" icon="report">
              {{ counters.failed }} · {{ $t('pipeops_alert_failed') }}
            </q-chip>
          </div>
        </div>

        <!-- Filters -->
        <div class="row q-col-gutter-md q-mb-md items-end">
          <q-select
            class="col-12 col-md-3"
            dense
            outlined
            clearable
            :label="$t('pipeops_filter_state')"
            :model-value="store.filters.state"
            :options="stateOptions"
            @update:model-value="(v) => store.applyFilters({ state: v })"
          />
          <q-select
            class="col-12 col-md-3"
            dense
            outlined
            clearable
            :label="$t('pipeops_filter_job_type')"
            :model-value="store.filters.job_type"
            :options="jobTypeOptions"
            @update:model-value="(v) => store.applyFilters({ job_type: v })"
          />
          <q-input
            class="col-6 col-md-1"
            dense
            outlined
            type="number"
            :label="$t('pipeops_filter_year')"
            :model-value="store.filters.year"
            @update:model-value="
              (v) => store.applyFilters({ year: v ? Number(v) : null })
            "
          />
          <q-input
            class="col-12 col-md-3"
            dense
            outlined
            debounce="400"
            :label="$t('pipeops_filter_search')"
            :model-value="store.filters.q"
            @update:model-value="
              (v) => store.applyFilters({ q: String(v ?? '') })
            "
          />
          <div class="col-auto">
            <q-toggle
              :model-value="store.filters.has_errors === true"
              :label="$t('pipeops_filter_has_errors')"
              @update:model-value="
                (v) => store.applyFilters({ has_errors: v ? true : null })
              "
            />
          </div>
          <div class="col-auto">
            <q-btn
              flat
              dense
              icon="restart_alt"
              :label="$t('pipeops_filter_clear')"
              @click="store.clearFilters()"
            />
          </div>
          <div class="col-auto">
            <q-btn
              flat
              dense
              icon="refresh"
              :label="$t('pipeops_refresh')"
              :loading="store.loading"
              @click="store.fetch()"
            />
          </div>
        </div>

        <q-banner v-if="store.error" class="bg-negative text-white q-mb-md">
          {{ store.error }}
        </q-banner>

        <q-markup-table flat bordered separator="cell">
          <thead>
            <tr>
              <th class="text-left" style="width: 36px"></th>
              <th class="text-left">{{ $t('pipeops_col_status') }}</th>
              <th class="text-left">{{ $t('pipeops_col_trigger') }}</th>
              <th class="text-left">{{ $t('pipeops_col_type') }}</th>
              <th class="text-left">{{ $t('pipeops_col_module') }}</th>
              <th class="text-left">{{ $t('pipeops_col_jobs') }}</th>
              <th class="text-left">{{ $t('pipeops_col_duration') }}</th>
              <th class="text-left">{{ $t('pipeops_col_when') }}</th>
              <th class="text-left">{{ $t('pipeops_col_author') }}</th>
              <th class="text-left">{{ $t('pipeops_col_message') }}</th>
              <th class="text-right" style="width: 96px">
                {{ $t('pipeops_col_actions') }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="store.loading && !store.items.length">
              <td colspan="11" class="text-center text-grey-7">
                {{ $t('pipeops_loading') }}
              </td>
            </tr>
            <tr v-else-if="!store.items.length">
              <td colspan="11" class="text-center text-grey-7">
                {{ $t('pipeops_empty') }}
              </td>
            </tr>
            <template v-for="p in store.items" :key="rowKey(p)">
              <tr class="cursor-pointer" @click="toggle(p)">
                <td>
                  <q-icon
                    :name="
                      expanded.has(rowKey(p)) ? 'expand_more' : 'chevron_right'
                    "
                  />
                </td>
                <td>
                  <q-badge
                    :color="STATUS_META[statusOf(p)].color"
                    text-color="white"
                  >
                    <q-icon
                      :name="STATUS_META[statusOf(p)].icon"
                      size="14px"
                      class="q-mr-xs"
                    />
                    {{ $t(STATUS_META[statusOf(p)].key) }}
                  </q-badge>
                </td>
                <td>
                  {{ p.job_type ?? '—' }}
                  <span
                    v-if="p.is_orphan"
                    class="text-caption text-grey-6 q-ml-xs"
                  >
                    {{ $t('pipeops_orphan_tag') }}
                  </span>
                </td>
                <td>{{ typeLabel(p) }}</td>
                <td>
                  {{ p.module_label ?? p.module_type_id ?? '—' }} /
                  {{ p.year ?? '—' }}
                </td>
                <td>
                  <!-- ``finished/total`` (FINISHED state count over total
                       job count).  Previously rendered
                       ``(total - errors)/total`` which always read "all
                       done" while jobs were still RUNNING.  Errors are
                       a separate suffix below. -->
                  {{ jobsFinishedCount(p) }}/{{ p.job_count }} ✓
                  <span v-if="p.error_count" class="text-negative">
                    · {{ p.error_count }}✗
                  </span>
                </td>
                <td>{{ fmtDuration(p.started_at, p.finished_at) }}</td>
                <td>{{ fmtWhen(p.started_at) }}</td>
                <td>{{ p.author ?? '—' }}</td>
                <td
                  class="text-grey-8 ellipsis"
                  :class="{ 'cursor-pointer': !!pipelineMessage(p) }"
                  style="max-width: 320px"
                  :title="$t('pipeops_msg_click_hint')"
                  @click.stop="openMsg(pipelineMessage(p))"
                >
                  {{ pipelineMessage(p) ?? '—' }}
                </td>
                <td class="text-right">
                  <!-- Processed-CSV download.  Visible whenever the
                       pipeline's parent ingest job has staged a
                       processed CSV — operator can grab the source
                       file to triage a failed/stalled run.  No
                       affordance when no job has the path (orphans,
                       API-only chains, in-flight chains before
                       phase 1 finalize). -->
                  <q-btn
                    v-if="processedCsvJob(p)"
                    flat
                    dense
                    round
                    color="positive"
                    icon="o_download"
                    size="sm"
                    @click.stop="downloadProcessedCsv(p)"
                  >
                    <q-tooltip>
                      {{ $t('pipeops_action_download_csv') }}
                    </q-tooltip>
                  </q-btn>
                  <!-- Abort the whole pipeline.  Mirrors the
                       data-management Cancel button (same backend
                       endpoint, same outcome) but gated behind a
                       confirmation dialog — the ops list shows many
                       rows and a misclick should be recoverable.
                       Only enabled while the pipeline is in flight
                       (statusOf === 'running'); on terminal rows
                       the button hides since there's nothing to
                       abort. -->
                  <q-btn
                    v-if="statusOf(p) === 'running' && p.pipeline_id !== null"
                    flat
                    dense
                    round
                    color="negative"
                    icon="cancel"
                    size="sm"
                    @click.stop="openAbortDialog(p)"
                  >
                    <q-tooltip>{{ $t('pipeops_action_abort') }}</q-tooltip>
                  </q-btn>
                </td>
              </tr>
              <tr v-if="expanded.has(rowKey(p))">
                <td colspan="11" class="bg-grey-1">
                  <div class="q-pa-sm">
                    <div v-for="j in p.jobs" :key="j.job_id" class="q-py-sm">
                      <!-- Main job row -->
                      <div class="row items-center no-wrap">
                        <q-badge
                          :color="jobColor(j)"
                          text-color="white"
                          class="q-mr-sm"
                        >
                          {{ j.state ?? '?'
                          }}{{ j.result ? ' · ' + j.result : '' }}
                        </q-badge>
                        <span class="text-weight-medium q-mr-sm">
                          #{{ j.job_id }} {{ j.job_type ?? '—' }}
                        </span>
                        <span class="text-caption text-grey-7 q-mr-sm">
                          {{
                            j.data_entry_type_label ??
                            (j.data_entry_type_id != null
                              ? 'det ' + j.data_entry_type_id
                              : '—')
                          }}
                          · {{ fmtDuration(j.started_at, j.finished_at) }}
                        </span>
                        <span
                          v-if="j.status_message"
                          class="text-caption text-grey-8 ellipsis cursor-pointer"
                          style="max-width: 520px"
                          :title="$t('pipeops_msg_click_hint')"
                          @click.stop="openMsg(j.status_message)"
                        >
                          {{ j.status_message }}
                        </span>
                      </div>

                      <!-- #2B — phase checklist (unit_sync etc.) -->
                      <div
                        v-if="jobPhases(j).length"
                        class="row items-center q-mt-xs q-gutter-xs q-pl-md"
                      >
                        <q-chip
                          v-for="ph in jobPhases(j)"
                          :key="ph.name"
                          :color="phaseColor(ph)"
                          text-color="white"
                          :icon="phaseIcon(ph)"
                          size="sm"
                          dense
                        >
                          {{ ph.name }}
                          <q-tooltip v-if="ph.error">{{ ph.error }}</q-tooltip>
                        </q-chip>
                      </div>

                      <!-- #2A — status_history timeline -->
                      <q-expansion-item
                        v-if="jobHistory(j).length"
                        dense
                        dense-toggle
                        class="q-mt-xs"
                        header-class="text-caption text-grey-7 q-pl-md"
                        :label="$t('pipeops_history_toggle')"
                        :caption="
                          $t('pipeops_history_count', {
                            n: jobHistory(j).length,
                          })
                        "
                      >
                        <div class="q-pl-lg">
                          <div
                            v-for="(h, idx) in jobHistory(j)"
                            :key="idx"
                            class="text-caption text-grey-8 q-py-xs"
                          >
                            <span class="text-grey-5 q-mr-xs">
                              {{ fmtTs(h.ts) }}
                            </span>
                            — {{ h.message }}
                          </div>
                        </div>
                      </q-expansion-item>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </q-markup-table>

        <div class="row items-center justify-end q-gutter-sm q-mt-md">
          <span class="text-caption text-grey-7">
            {{ store.offset + 1 }}–{{ store.offset + store.items.length }} /
            {{ store.total }}
          </span>
          <q-btn
            flat
            dense
            icon="chevron_left"
            :disable="store.offset === 0 || store.loading"
            @click="store.setPage(store.offset - store.limit)"
          />
          <q-btn
            flat
            dense
            icon="chevron_right"
            :disable="
              store.offset + store.limit >= store.total || store.loading
            "
            @click="store.setPage(store.offset + store.limit)"
          />
        </div>
      </div>
    </div>

    <!-- Abort confirmation — one-click guard against misfire on a long
         chain.  The data-management page button skips this because
         it's scoped to a single visible card; the ops list shows
         many rows and a misclick is easy. -->
    <q-dialog v-model="abortDialog" persistent>
      <q-card style="min-width: 360px">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-h6">{{ $t('pipeops_abort_title') }}</div>
          <q-space />
          <q-btn
            flat
            size="md"
            icon="o_close"
            color="grey-6"
            :disable="aborting"
            @click="abortDialog = false"
          />
        </q-card-section>
        <q-separator />
        <q-card-section>
          <div class="text-body2 text-grey-8">
            {{ $t('pipeops_abort_body') }}
          </div>
          <div v-if="abortTarget" class="q-mt-sm text-caption text-grey-7">
            #{{ abortTarget.latest_job_id }} ·
            {{ abortTarget.job_type ?? '—' }} ·
            {{ abortTarget.module_label ?? abortTarget.module_type_id ?? '—' }}
            / {{ abortTarget.year ?? '—' }}
          </div>
        </q-card-section>
        <q-card-actions class="q-px-md q-pb-md">
          <q-btn
            flat
            :label="$t('pipeops_abort_cancel')"
            :disable="aborting"
            @click="abortDialog = false"
          />
          <q-btn
            color="negative"
            unelevated
            :label="$t('pipeops_abort_confirm')"
            :loading="aborting"
            @click="confirmAbort"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- UI1 — full message + copy to clipboard -->
    <q-dialog v-model="msgDialog">
      <q-card style="min-width: 480px; max-width: 90vw">
        <q-card-section class="row items-center q-pb-none">
          <div class="text-subtitle1">{{ $t('pipeops_msg_title') }}</div>
          <q-space />
          <q-btn v-close-popup flat size="md" icon="o_close" color="grey-6" />
        </q-card-section>
        <q-separator />
        <q-card-section>
          <pre
            class="q-pa-md bg-grey-2 rounded-borders"
            style="
              white-space: pre-wrap;
              word-break: break-word;
              max-height: 60vh;
              overflow: auto;
              margin: 0;
            "
            >{{ msgText }}</pre
          >
        </q-card-section>
        <q-card-actions class="q-px-md q-pb-md">
          <q-btn
            flat
            icon="content_copy"
            :label="$t('pipeops_msg_copy')"
            @click="copyMsg"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>
