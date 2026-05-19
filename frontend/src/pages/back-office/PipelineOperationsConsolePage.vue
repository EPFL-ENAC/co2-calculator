<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import {
  usePipelineOperationsConsole,
  type PipelineListItem,
} from 'src/stores/pipelineOperationsConsole';

const store = usePipelineOperationsConsole();

const expanded = ref<Set<string>>(new Set());

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

type StatusKind = 'failed' | 'running' | 'partial' | 'done';

function statusOf(p: PipelineListItem): StatusKind {
  if (p.progress.has_error) return 'failed';
  if (!p.progress.done) return 'running';
  if (p.error_count > 0) return 'partial';
  return 'done';
}

const STATUS_META: Record<
  StatusKind,
  { color: string; icon: string; key: string }
> = {
  failed: { color: 'negative', icon: 'error', key: 'pipeops_status_failed' },
  running: { color: 'primary', icon: 'sync', key: 'pipeops_status_running' },
  partial: { color: 'warning', icon: 'warning', key: 'pipeops_status_partial' },
  done: { color: 'positive', icon: 'check_circle', key: 'pipeops_status_done' },
};

function jobColor(j: { state: string | null; result: string | null }): string {
  if (j.state !== 'FINISHED') return 'grey';
  if (j.result === 'ERROR') return 'negative';
  if (j.result === 'WARNING') return 'warning';
  return 'positive';
}

function fmtDuration(a: string | null, b: string | null): string {
  if (!a) return '—';
  const start = new Date(a).getTime();
  const end = b ? new Date(b).getTime() : Date.now();
  const s = Math.max(0, Math.round((end - start) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m${String(s % 60).padStart(2, '0')}s`;
  return `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}m`;
}

function fmtWhen(s: string | null): string {
  if (!s) return '—';
  return new Date(s).toLocaleString();
}

const counters = computed(() => store.counters);

const stateOptions = ['NOT_STARTED', 'QUEUED', 'RUNNING', 'FINISHED'];
const resultOptions = ['SUCCESS', 'WARNING', 'ERROR'];
const jobTypeOptions = [
  'csv_ingest',
  'factor_ingest',
  'api_ingest',
  'emission_recalc',
  'aggregation',
  'unit_sync',
];

onMounted(() => {
  void store.fetch();
});
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_PIPELINE_OPERATIONS" />
    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <div class="text-body1 q-mb-lg">{{ $t('pipeops_subtitle') }}</div>

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
            class="col-12 col-md-2"
            dense
            outlined
            clearable
            :label="$t('pipeops_filter_state')"
            :model-value="store.filters.state"
            :options="stateOptions"
            @update:model-value="(v) => store.applyFilters({ state: v })"
          />
          <q-select
            class="col-12 col-md-2"
            dense
            outlined
            clearable
            :label="$t('pipeops_filter_result')"
            :model-value="store.filters.result"
            :options="resultOptions"
            @update:model-value="(v) => store.applyFilters({ result: v })"
          />
          <q-select
            class="col-12 col-md-2"
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
              <th class="text-left">{{ $t('pipeops_col_module') }}</th>
              <th class="text-left">{{ $t('pipeops_col_jobs') }}</th>
              <th class="text-left">{{ $t('pipeops_col_duration') }}</th>
              <th class="text-left">{{ $t('pipeops_col_when') }}</th>
              <th class="text-left">{{ $t('pipeops_col_message') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="store.loading && !store.items.length">
              <td colspan="8" class="text-center text-grey-7">
                {{ $t('pipeops_loading') }}
              </td>
            </tr>
            <tr v-else-if="!store.items.length">
              <td colspan="8" class="text-center text-grey-7">
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
                <td>{{ p.module_type_id ?? '—' }} / {{ p.year ?? '—' }}</td>
                <td>
                  {{ p.job_count - p.error_count }}/{{ p.job_count }} ✓
                  <span v-if="p.error_count" class="text-negative">
                    · {{ p.error_count }}✗
                  </span>
                </td>
                <td>{{ fmtDuration(p.started_at, p.finished_at) }}</td>
                <td>{{ fmtWhen(p.started_at) }}</td>
                <td
                  class="text-grey-8 ellipsis"
                  style="max-width: 320px"
                  :title="p.status_message ?? ''"
                >
                  {{ p.status_message ?? '—' }}
                </td>
              </tr>
              <tr v-if="expanded.has(rowKey(p))">
                <td colspan="8" class="bg-grey-1">
                  <div class="q-pa-sm">
                    <div
                      v-for="j in p.jobs"
                      :key="j.job_id"
                      class="row items-center q-py-xs no-wrap"
                    >
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
                        det {{ j.data_entry_type_id ?? '—' }} ·
                        {{ fmtDuration(j.started_at, j.finished_at) }}
                      </span>
                      <span
                        v-if="j.status_message"
                        class="text-caption text-grey-8 ellipsis"
                        style="max-width: 520px"
                        :title="j.status_message"
                      >
                        {{ j.status_message }}
                      </span>
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
  </q-page>
</template>
