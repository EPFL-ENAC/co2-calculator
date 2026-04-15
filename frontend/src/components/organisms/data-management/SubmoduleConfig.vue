<script setup lang="ts">
import { ref, computed, inject, type Ref } from 'vue';
import { MODULES } from 'src/constant/modules';
import {
  useBackofficeDataManagement,
  IngestionResult,
  IngestionState,
  IngestionMethod,
  TargetType,
  type ImportRow,
  type SyncJobResponse,
  type RecalculationStatus,
  type JobUpdatePayload,
} from 'src/stores/backofficeDataManagement';
import { useYearConfigStore, type SyncJobSummary } from 'src/stores/yearConfig';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import {
  MODULE_SUBMODULES,
  type SubmoduleConfig,
} from 'src/constant/backoffice-module-config';

const props = defineProps<{
  module: string;
  selectedYear: number;
}>();

const { t: $t } = useI18n();
const yearConfigStore = useYearConfigStore();
const backofficeDataManagement = useBackofficeDataManagement();
const { isSubmoduleEnabled, isSubmoduleIncomplete } = yearConfigStore;

// ── Injected from ModuleConfig ────────────────────────────────────────────────

const openDataEntryDialog = inject<
  (row: ImportRow, targetType: TargetType | null) => void
>('openDataEntryDialog')!;

const getRecalcStatus =
  inject<(sub: SubmoduleConfig) => RecalculationStatus | undefined>(
    'getRecalcStatus',
  )!;

const handleJobCompleted = inject<() => Promise<void>>('handleJobCompleted')!;
const handleJobProgressing = inject<() => Promise<void>>(
  'handleJobProgressing',
)!;

const recalcTypeRunning =
  inject<Ref<Record<string, boolean>>>('recalcTypeRunning')!;

const triggerTypeRecalculation = inject<
  (sub: SubmoduleConfig) => Promise<void>
>('triggerTypeRecalculation')!;

// ── Import row helpers ────────────────────────────────────────────────────────

const QUASAR_COLOR_MAP: Record<string, string> = {
  accent: 'var(--q-accent)',
  positive: 'var(--q-positive)',
  negative: 'var(--q-negative)',
  warning: 'var(--q-warning)',
  'grey-4': '#bdbdbd',
};

function findJob(
  jobs: SyncJobSummary[],
  moduleTypeId: number,
  targetType: number | null,
  dataEntryTypeId?: number,
  ingestionMethod?: IngestionMethod,
): SyncJobSummary | undefined {
  const candidates = jobs.filter(
    (j) => j.module_type_id === moduleTypeId && j.target_type === targetType,
  );
  if (dataEntryTypeId !== undefined) {
    return candidates.find(
      (j) =>
        j.data_entry_type_id === dataEntryTypeId &&
        j.ingestion_method === ingestionMethod?.valueOf(),
    );
  }
  return candidates[0];
}

function toSyncJobResponse(job: SyncJobSummary): SyncJobResponse {
  return {
    job_id: job.job_id,
    module_type_id: job.module_type_id,
    data_entry_type_id: job.data_entry_type_id,
    year: job.year,
    target_type: job.target_type as TargetType,
    state: job.state as IngestionState,
    result: job.result as IngestionResult,
    status_message: job.status_message,
    meta: job.meta,
  };
}

function getImportRow(sub: SubmoduleConfig): ImportRow {
  const jobs = yearConfigStore.latestJobs;
  const dataJob = findJob(
    jobs,
    sub.moduleTypeId,
    0,
    sub.dataEntryTypeId,
    IngestionMethod.CSV,
  );
  const apiDataJob = sub.hasApi
    ? findJob(
        jobs,
        sub.moduleTypeId,
        0,
        sub.dataEntryTypeId,
        IngestionMethod.API,
      )
    : undefined;
  const factorJob = findJob(
    jobs,
    sub.moduleTypeId,
    1,
    sub.dataEntryTypeId,
    IngestionMethod.CSV,
  );
  return {
    key: sub.key,
    labelKey: sub.labelKey,
    moduleTypeId: sub.moduleTypeId,
    dataEntryTypeId: sub.dataEntryTypeId,
    hasData: !sub.noData,
    hasFactors: !sub.noFactors,
    hasApi: sub.hasApi ?? false,
    other: sub.other,
    hasOtherUpload: !!sub.other,
    isDisabled: sub.isDisabled ?? false,
    lastDataJob: dataJob ? toSyncJobResponse(dataJob) : undefined,
    lastFactorJob: factorJob ? toSyncJobResponse(factorJob) : undefined,
    lastApiDataJob: apiDataJob ? toSyncJobResponse(apiDataJob) : undefined,
  };
}

function submoduleShowsImportRow(sub: SubmoduleConfig): boolean {
  const row = getImportRow(sub);
  return row.hasData || row.hasFactors || row.hasOtherUpload;
}

function cardStyle(color: string): string {
  if (color === 'positive') {
    const c = QUASAR_COLOR_MAP['positive'];
    return `border: 1px solid ${c}; background-color: color-mix(in srgb, ${c} 10%, transparent)`;
  }
  return 'border: 1px solid rgba(0,0,0,0.12)';
}

function dataButtonColor(row: ImportRow): string {
  if (row.isDisabled) return 'grey-4';
  if (!row.lastDataJob) return 'accent';
  if (row.lastDataJob.result === 2) return 'negative';
  if (row.lastDataJob.result === 1) return 'warning';
  return 'positive';
}

function factorButtonColor(row: ImportRow): string {
  if (row.isDisabled) return 'grey-4';
  if (!row.lastFactorJob) return 'accent';
  if (row.lastFactorJob.result === 2) return 'negative';
  if (row.lastFactorJob.result === 1) return 'warning';
  return 'positive';
}

function dataButtonLabel(row: ImportRow): string {
  if (row.isDisabled) return '';
  return row.lastDataJob
    ? $t('data_management_reupload_data')
    : $t('data_management_add_data');
}

function factorButtonLabel(row: ImportRow): string {
  if (row.isDisabled) return '';
  return row.lastFactorJob
    ? $t('data_management_reupload_factors')
    : $t('data_management_add_factors');
}

function downloadLastCsv(row: ImportRow, targetType: TargetType) {
  const job =
    targetType === TargetType.DATA_ENTRIES
      ? row.lastDataJob
      : row.lastFactorJob;
  if (!job?.meta) return;
  const filePath = (job.meta as Record<string, unknown>)
    .processed_file_path as string;
  if (!filePath) return;
  const a = document.createElement('a');
  a.href = `/api/v1/files/${filePath}`;
  a.download = filePath.split('/').pop() || filePath;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function safeFileName(meta: unknown): string | undefined {
  const fp = (meta as Record<string, unknown>)?.file_path as string | undefined;
  if (!fp) return undefined;
  const parts = fp.split('/');
  return parts.length ? parts[parts.length - 1] : fp;
}

// ── Submodule config helpers ──────────────────────────────────────────────────

async function updateSubmoduleEnabled(
  sub: SubmoduleConfig,
  value: boolean,
): Promise<void> {
  const moduleKey = String(sub.moduleTypeId);
  const subKey =
    sub.dataEntryTypeId !== undefined ? String(sub.dataEntryTypeId) : undefined;
  if (!subKey) return;
  try {
    await yearConfigStore.updateConfig(props.selectedYear, {
      config: {
        modules: {
          [moduleKey]: { submodules: { [subKey]: { enabled: value } } },
        },
      },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({ type: 'negative', message: $t('year_config_save_error') });
  }
}

function getSubmoduleThreshold(sub: SubmoduleConfig): number | null {
  const moduleKey = String(sub.moduleTypeId);
  const subKey =
    sub.dataEntryTypeId !== undefined ? String(sub.dataEntryTypeId) : undefined;
  if (!subKey) return null;
  const moduleConfig = yearConfigStore.config?.config?.modules?.[moduleKey];
  return moduleConfig?.submodules?.[subKey]?.threshold ?? null;
}

async function updateSubmoduleThreshold(
  sub: SubmoduleConfig,
  value: number | null,
): Promise<void> {
  const moduleKey = String(sub.moduleTypeId);
  const subKey =
    sub.dataEntryTypeId !== undefined ? String(sub.dataEntryTypeId) : undefined;
  if (!subKey) return;
  const existingModule = yearConfigStore.config?.config?.modules?.[moduleKey];
  if (!existingModule) return;
  const existingSub = existingModule.submodules?.[subKey];
  if (!existingSub) return;
  try {
    await yearConfigStore.updateConfig(props.selectedYear, {
      config: {
        modules: {
          [moduleKey]: {
            ...existingModule,
            submodules: {
              ...existingModule.submodules,
              [subKey]: { ...existingSub, threshold: value },
            },
          },
        },
      },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({ type: 'negative', message: $t('year_config_save_error') });
  }
}

// ── Dialog: computed factor sync ──────────────────────────────────────────────

const showComputedFactorConfirm = ref(false);
const pendingComputedFactorSub = ref<SubmoduleConfig | null>(null);
const computedFactorRunning = ref<Record<string, boolean>>({});
const anyComputedFactorRunning = computed(() =>
  Object.values(computedFactorRunning.value).some(Boolean),
);

function openComputedFactorConfirm(sub: SubmoduleConfig): void {
  pendingComputedFactorSub.value = sub;
  showComputedFactorConfirm.value = true;
}

async function confirmComputedFactorSync(): Promise<void> {
  const sub = pendingComputedFactorSub.value;
  if (!sub || sub.dataEntryTypeId === undefined) return;
  showComputedFactorConfirm.value = false;
  computedFactorRunning.value[sub.key] = true;
  try {
    const jobId = await backofficeDataManagement.initiateComputedFactorSync(
      sub.moduleTypeId,
      sub.dataEntryTypeId,
      props.selectedYear,
    );
    backofficeDataManagement.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        const result = payload?.result;
        if (result === IngestionResult.WARNING) {
          Notify.create({
            type: 'warning',
            message: $t('data_management_compute_factors_warning'),
            caption: payload?.status_message ?? '',
            position: 'top',
            timeout: 5000,
          });
        } else if (result === IngestionResult.SUCCESS) {
          Notify.create({
            type: 'positive',
            message: $t('data_management_compute_factors_success'),
            position: 'top',
            timeout: 5000,
          });
        } else {
          Notify.create({
            type: 'negative',
            message: $t('data_management_compute_factors_error'),
            caption: payload?.status_message ?? '',
            position: 'top',
            timeout: 5000,
          });
        }
        computedFactorRunning.value[sub.key] = false;
        void handleJobCompleted();
      },
      (payload?: JobUpdatePayload) => {
        Notify.create({
          type: 'negative',
          message: $t('data_management_compute_factors_error'),
          caption: payload?.status_message ?? '',
          position: 'top',
          timeout: 5000,
        });
        computedFactorRunning.value[sub.key] = false;
        void handleJobCompleted();
      },
      () => {
        computedFactorRunning.value[sub.key] = false;
      },
      () => {
        void handleJobProgressing();
      },
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '';
    Notify.create({
      type: 'negative',
      message: $t('data_management_compute_factors_error'),
      caption: msg,
      position: 'top',
    });
    computedFactorRunning.value[sub.key] = false;
  }
}
</script>
<template>
  <q-expansion-item
    v-for="submodule in MODULE_SUBMODULES[module] ?? []"
    :key="submodule.key"
    expand-separator
    class="bg-white rounded-borders"
    style="border: 1px solid rgba(0, 0, 0, 0.12)"
  >
    <template #header>
      <q-item-section>
        <div class="row items-center q-gutter-sm">
          <span
            class="text-body2 text-weight-medium"
            :class="!isSubmoduleEnabled(submodule) ? 'text-grey-6' : ''"
            >{{ $t(submodule.labelKey) }}</span
          >
          <q-badge
            v-if="
              submodule.dataEntryTypeId !== undefined &&
              getRecalcStatus(submodule)?.needs_recalculation
            "
            outline
            rounded
            color="warning"
            class="text-weight-medium"
            :label="$t('data_management_recalculation_needed')"
          />
          <q-badge
            v-if="
              isSubmoduleEnabled(submodule) && isSubmoduleIncomplete(submodule)
            "
            outline
            rounded
            color="accent"
            class="text-weight-medium"
            :label="$t('common_filter_incomplete')"
          />
        </div>
      </q-item-section>
    </template>
    <q-separator class="q-mb-xs" />
    <template v-if="!submodule.factorsOnly">
      <q-card flat class="col q-px-lg q-pt-lg q-pb-md">
        <div class="row items-center q-mb-xs">
          <q-icon
            name="power_settings_new"
            color="accent"
            size="xs"
            class="q-mr-sm"
          />
          <div class="text-body2 text-weight-medium">
            {{ $t('data_management_submodule_activation_title') }}
          </div>
        </div>
        <div class="text-caption text-secondary q-mb-sm">
          {{ $t('data_management_submodule_activation_description') }}
        </div>
        <q-toggle
          :model-value="isSubmoduleEnabled(submodule)"
          color="accent"
          keep-color
          size="md"
          @update:model-value="
            (val: boolean) => updateSubmoduleEnabled(submodule, val)
          "
        />
      </q-card>
      <q-separator class="q-my-xs" />
      <q-card
        flat
        class="col q-px-lg q-pt-lg q-pb-md"
        :style="
          !isSubmoduleEnabled(submodule)
            ? 'opacity: 0.45; pointer-events: none'
            : undefined
        "
      >
        <div class="row items-center q-mb-xs">
          <q-icon
            name="legend_toggle"
            color="accent"
            size="xs"
            class="q-mr-sm"
          />
          <div class="text-body2 text-weight-medium">
            {{ $t('data_management_threshold_title') }}
          </div>
        </div>
        <div class="text-caption text-secondary q-mb-sm">
          {{ $t('data_management_threshold_description') }}
        </div>
        <q-input
          :model-value="getSubmoduleThreshold(submodule)"
          type="number"
          dense
          outlined
          size="md"
          :debounce="600"
          :suffix="$t('tco2eq')"
          :placeholder="$t('no_threshold')"
          style="max-width: 500px"
          @update:model-value="
            (val: string | number | null) =>
              updateSubmoduleThreshold(
                submodule,
                val === '' || val === null ? null : Number(val),
              )
          "
        />
      </q-card>
      <q-separator v-if="submoduleShowsImportRow(submodule)" class="q-my-xs" />
    </template>
    <div
      v-if="submoduleShowsImportRow(submodule)"
      class="row q-pa-md"
      :style="[
        { gap: '1rem' },
        !isSubmoduleEnabled(submodule)
          ? { opacity: 0.45, pointerEvents: 'none' }
          : {},
      ]"
    >
      <!-- Data -->
      <q-card
        v-if="getImportRow(submodule).hasData"
        flat
        class="col q-pa-lg"
        :style="cardStyle(dataButtonColor(getImportRow(submodule)))"
      >
        <div class="text-body2 text-weight-bold q-mb-xs">
          {{ $t('data_management_data') }}
        </div>
        <div class="text-caption text-secondary q-mb-md">
          {{ $t('data_management_data_description') }}
        </div>
        <div class="row items-center" style="gap: 0.5rem">
          <q-spinner-rings
            v-if="
              getImportRow(submodule).lastDataJob?.state ===
              IngestionState.RUNNING
            "
            color="grey"
          />
          <q-btn
            :color="dataButtonColor(getImportRow(submodule))"
            icon="add"
            size="sm"
            :label="dataButtonLabel(getImportRow(submodule))"
            class="text-weight-medium"
            :disable="getImportRow(submodule).isDisabled"
            @click="
              openDataEntryDialog(
                getImportRow(submodule),
                TargetType.DATA_ENTRIES,
              )
            "
          />
          <!-- Per-type emission recalculation button -->
          <template
            v-if="
              submodule.dataEntryTypeId !== undefined &&
              getImportRow(submodule).hasFactors
            "
          >
            <q-spinner-rings
              v-if="
                recalcTypeRunning[
                  `${submodule.moduleTypeId}-${submodule.dataEntryTypeId}`
                ]
              "
              color="grey"
            />
            <template v-else>
              <q-btn
                color="accent"
                outline
                icon="refresh"
                :icon-right="
                  getRecalcStatus(submodule)?.needs_recalculation
                    ? 'warning'
                    : undefined
                "
                size="sm"
                :label="$t('data_management_recalculate_emissions')"
                :title="
                  getRecalcStatus(submodule)?.needs_recalculation
                    ? $t('data_management_recalculation_needed')
                    : ''
                "
                class="text-weight-medium"
                :disable="getImportRow(submodule).isDisabled"
                @click="triggerTypeRecalculation(submodule)"
              />
            </template>
          </template>
        </div>
      </q-card>

      <!-- Factors -->
      <q-card
        v-if="getImportRow(submodule).hasFactors"
        flat
        class="col q-pa-lg"
        :style="cardStyle(factorButtonColor(getImportRow(submodule)))"
      >
        <div class="row items-center q-mb-xs">
          <div class="text-body2 text-weight-bold">
            {{ $t('data_management_factor') }}
          </div>
          <q-space />
          <span class="text-caption text-grey-5"
            ><span class="text-negative">*</span
            >{{ $t('common_mandatory') }}</span
          >
        </div>
        <div
          v-if="module === 'headcount'"
          class="text-caption text-secondary q-mb-md"
        >
          {{ $t('data_management_factor_headcount_description') }}
        </div>
        <div v-else class="text-caption text-secondary q-mb-md">
          {{ $t('data_management_factor_description') }}
        </div>
        <div class="row justify-between items-center full-width">
          <div class="row items-center" style="gap: 0.5rem">
            <q-spinner-rings
              v-if="
                getImportRow(submodule).lastFactorJob?.state ===
                IngestionState.RUNNING
              "
              color="grey"
            />
            <q-btn
              :color="factorButtonColor(getImportRow(submodule))"
              icon="add"
              size="sm"
              :label="factorButtonLabel(getImportRow(submodule))"
              class="text-weight-medium"
              :disable="getImportRow(submodule).isDisabled"
              @click="
                openDataEntryDialog(getImportRow(submodule), TargetType.FACTORS)
              "
            />
            <template v-if="module === MODULES.ResearchFacilities">
              <q-spinner-rings
                v-if="computedFactorRunning[submodule.key]"
                color="grey"
              />
              <q-btn
                v-else
                color="accent"
                outline
                icon="calculate"
                size="sm"
                :label="$t('data_management_compute_factors')"
                class="text-weight-medium"
                :disable="
                  getImportRow(submodule).isDisabled || anyComputedFactorRunning
                "
                @click="openComputedFactorConfirm(submodule)"
              />
            </template>
          </div>
          <div
            v-if="getImportRow(submodule).lastFactorJob?.meta"
            class="row items-center no-wrap"
            style="gap: 0.75rem"
          >
            <div class="column items-end">
              <div class="row items-center text-body2 text-weight-medium">
                <span class="text-positive q-mr-xs">✓</span>
                {{ safeFileName(getImportRow(submodule).lastFactorJob?.meta) }}
              </div>
              <div class="text-caption text-grey-7">
                {{
                  getImportRow(submodule).lastFactorJob?.meta?.rows_processed
                }}
                {{ $t('data_management_rows_imported') }}
                <span
                  v-if="getImportRow(submodule).lastFactorJob?.meta?.timestamp"
                >
                  •
                  {{
                    new Date(
                      getImportRow(submodule).lastFactorJob.meta
                        .timestamp as string,
                    ).toLocaleDateString()
                  }}
                </span>
              </div>
            </div>
            <q-btn
              color="positive"
              icon="o_download"
              size="sm"
              unelevated
              dense
              @click="
                downloadLastCsv(getImportRow(submodule), TargetType.FACTORS)
              "
            >
              <q-tooltip>{{
                $t('data_management_download_last_csv')
              }}</q-tooltip>
            </q-btn>
            <q-icon
              v-if="
                getImportRow(submodule).lastFactorJob?.result ===
                  IngestionResult.WARNING ||
                getImportRow(submodule).lastFactorJob?.result ===
                  IngestionResult.ERROR
              "
              name="info"
              size="sm"
              class="cursor-pointer"
            >
              <q-tooltip>
                <div class="text-left">
                  {{ getImportRow(submodule).lastFactorJob?.status_message }}:
                  <span
                    v-if="
                      getImportRow(submodule).lastFactorJob?.meta?.error !==
                      getImportRow(submodule).lastFactorJob?.status_message
                    "
                    class="text-negative"
                  >
                    {{
                      getImportRow(submodule).lastFactorJob?.meta?.error || ''
                    }}
                  </span>
                  <hr />
                  <div
                    v-for="(key, value, index) in getImportRow(submodule)
                      .lastFactorJob?.meta?.stats || []"
                    :key="index"
                  >
                    {{ key }}: {{ value }}
                  </div>
                </div>
              </q-tooltip>
            </q-icon>
          </div>
        </div>
        <div
          v-if="
            getImportRow(submodule).lastFactorJob?.result ===
              IngestionResult.WARNING ||
            getImportRow(submodule).lastFactorJob?.result ===
              IngestionResult.ERROR
          "
          class="q-mt-md q-pa-md bg-grey-2 rounded-borders"
        >
          <div class="text-body2 text-weight-bold q-mb-sm text-negative">
            {{ getImportRow(submodule).lastFactorJob?.status_message }}
          </div>
          <div
            v-if="
              getImportRow(submodule).lastFactorJob?.meta?.error !==
              getImportRow(submodule).lastFactorJob?.status_message
            "
            class="text-body2 q-mb-md"
          >
            {{ getImportRow(submodule).lastFactorJob?.meta?.error }}
          </div>
          <div
            v-for="(key, value, index) in getImportRow(submodule).lastFactorJob
              ?.meta?.stats || []"
            :key="index"
            class="text-caption text-grey-7"
          >
            {{ key }}: {{ value }}
          </div>
        </div>
      </q-card>

      <!-- References -->
      <q-card
        v-if="getImportRow(submodule).hasOtherUpload"
        flat
        class="col q-pa-lg"
      >
        <div class="row items-center q-mb-xs">
          <div class="text-body2 text-weight-bold">
            {{ $t('data_management_references') }}
          </div>
          <q-space />
          <span class="text-caption text-grey-5"
            ><span class="text-negative">*</span
            >{{ $t('common_mandatory') }}</span
          >
        </div>
        <div class="text-caption text-secondary q-mb-md">
          {{ $t('data_management_references_description') }}
        </div>
        <div class="q-mb-xs text-caption text-grey-7">
          {{ $t(getImportRow(submodule).other!) }}
        </div>
        <q-btn
          no-caps
          outline
          color="accent"
          icon="file_upload"
          size="sm"
          :label="$t('data_management_upload_reference')"
          class="text-weight-medium"
          disable
        >
          <q-tooltip>{{ $t('data_management_tbd') }}</q-tooltip>
        </q-btn>
      </q-card>
    </div>
  </q-expansion-item>

  <!-- Computed factor sync confirmation dialog (Research Facilities) -->
  <q-dialog v-model="showComputedFactorConfirm" persistent>
    <q-card style="min-width: 420px">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="calculate" color="accent" size="sm" class="q-mr-sm" />
        <div class="text-h6">
          {{ $t('data_management_compute_factors_confirm_title') }}
        </div>
      </q-card-section>
      <q-card-section class="text-body2">
        {{ $t('data_management_compute_factors_confirm_message') }}
      </q-card-section>
      <q-card-actions align="right">
        <q-btn
          flat
          :label="$t('common_cancel')"
          @click="showComputedFactorConfirm = false"
        />
        <q-btn
          color="accent"
          unelevated
          :label="$t('common_confirm')"
          @click="confirmComputedFactorSync()"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
