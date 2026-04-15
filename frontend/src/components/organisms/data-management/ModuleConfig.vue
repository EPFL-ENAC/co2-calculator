<script setup lang="ts">
import { ref, onMounted, watch, provide } from 'vue';

import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import DataEntryDialog from 'src/components/organisms/data-management/DataEntryDialog.vue';
import SubmoduleConfig from 'src/components/organisms/data-management/SubmoduleConfig.vue';
import {
  MODULE_SUBMODULES,
  MODULE_COMMON_UPLOADS,
  type SubmoduleConfig as SubmoduleConfigItem,
} from '../../../constant/backoffice-module-config';

import {
  useBackofficeDataManagement,
  IngestionResult,
  IngestionState,
  IngestionMethod,
  TargetType,
  type ImportRow,
  type SyncJobResponse,
  type JobUpdatePayload,
  type ModuleRecalculationStatus,
  type RecalculationStatus,
} from 'src/stores/backofficeDataManagement';
import {
  useYearConfigStore,
  type SyncJobSummary,
  type ModuleConfig as ModuleConfigType,
} from 'src/stores/yearConfig';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';

type UncertaintyTag = ModuleConfigType['uncertainty_tag'];

const QUASAR_COLOR_MAP: Record<string, string> = {
  accent: 'var(--q-accent)',
  positive: 'var(--q-positive)',
  negative: 'var(--q-negative)',
  warning: 'var(--q-warning)',
  'grey-4': '#bdbdbd',
};

const props = defineProps<{
  module: string;
  selectedYear: number;
}>();

const { t: $t } = useI18n();
const yearConfigStore = useYearConfigStore();
const backofficeDataManagement = useBackofficeDataManagement();

const expanded = ref(false);

// ── Import row helpers ────────────────────────────────────────────────────────

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

function getImportRow(sub: SubmoduleConfigItem): ImportRow {
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

// ── Module / submodule config helpers ────────────────────────────────────────

function getModuleTypeIdFromName(module: string): number {
  const subs =
    MODULE_SUBMODULES[module as keyof typeof MODULE_SUBMODULES] ?? [];
  return subs.length > 0 ? subs[0].moduleTypeId : 0;
}

function isModuleEnabled(module: string): boolean {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return true;
  const moduleConfig =
    yearConfigStore.config?.config?.modules?.[String(moduleTypeId)];
  return moduleConfig?.enabled ?? true;
}

async function updateModuleEnabled(
  module: string,
  value: boolean,
): Promise<void> {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return;
  try {
    await yearConfigStore.updateConfig(props.selectedYear, {
      config: { modules: { [String(moduleTypeId)]: { enabled: value } } },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({ type: 'negative', message: $t('year_config_save_error') });
  }
}

function isSubmoduleEnabled(sub: SubmoduleConfigItem): boolean {
  const moduleKey = String(sub.moduleTypeId);
  const subKey =
    sub.dataEntryTypeId !== undefined ? String(sub.dataEntryTypeId) : undefined;
  if (!subKey) return true;
  const moduleConfig = yearConfigStore.config?.config?.modules?.[moduleKey];
  return moduleConfig?.submodules?.[subKey]?.enabled ?? true;
}

function getModuleUncertainty(module: string): UncertaintyTag {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return 'medium';
  const moduleConfig =
    yearConfigStore.config?.config?.modules?.[String(moduleTypeId)];
  return moduleConfig?.uncertainty_tag ?? 'medium';
}

async function updateModuleUncertainty(
  module: string,
  value: UncertaintyTag,
): Promise<void> {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return;
  try {
    await yearConfigStore.updateConfig(props.selectedYear, {
      config: {
        modules: { [String(moduleTypeId)]: { uncertainty_tag: value } },
      },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({ type: 'negative', message: $t('year_config_save_error') });
  }
}

function isModuleIncomplete(module: string): boolean {
  if (!isModuleEnabled(module)) return false;
  const submodules =
    MODULE_SUBMODULES[module as keyof typeof MODULE_SUBMODULES] ?? [];
  if (submodules.length === 0) return false;
  return submodules.some((sub) => {
    if (!isSubmoduleEnabled(sub)) return false;
    const row = getImportRow(sub);
    const dataIncomplete =
      row.hasData && (!row.lastDataJob || row.lastDataJob.result !== 0);
    const factorsIncomplete =
      row.hasFactors && (!row.lastFactorJob || row.lastFactorJob.result !== 0);
    const referencesIncomplete =
      row.hasOtherUpload && (!row.lastDataJob || row.lastDataJob.result !== 0);
    return dataIncomplete || factorsIncomplete || referencesIncomplete;
  });
}

// ── Dialog: data entry ────────────────────────────────────────────────────────

const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

function openDataEntryDialog(row: ImportRow, targetType: TargetType | null) {
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
}

// ── Recalculation status ──────────────────────────────────────────────────────

const recalculationStatus = ref<Record<number, ModuleRecalculationStatus>>({});
const recalcRunning = ref<Record<number, boolean>>({});
const recalcTypeRunning = ref<Record<string, boolean>>({});

async function refreshRecalculationStatus(): Promise<void> {
  const statuses = await backofficeDataManagement.fetchRecalculationStatus(
    props.selectedYear,
  );
  const map: Record<number, ModuleRecalculationStatus> = {};
  for (const s of statuses) {
    map[s.module_type_id] = s;
  }
  recalculationStatus.value = map;
}

function getRecalcStatus(
  sub: SubmoduleConfigItem,
): RecalculationStatus | undefined {
  if (sub.dataEntryTypeId === undefined) return undefined;
  return recalculationStatus.value[sub.moduleTypeId]?.data_entry_types.find(
    (d) => d.data_entry_type_id === sub.dataEntryTypeId,
  );
}

// ── Dialog: module recalculation ──────────────────────────────────────────────

const showRecalcDialog = ref(false);
const recalcDialogModuleTypeId = ref<number | null>(null);
const recalcOnlyStale = ref(true);

function openRecalcDialog(moduleTypeId: number): void {
  recalcDialogModuleTypeId.value = moduleTypeId;
  recalcOnlyStale.value = true;
  showRecalcDialog.value = true;
}

function staleTypesForModule(moduleTypeId: number): RecalculationStatus[] {
  return (
    recalculationStatus.value[moduleTypeId]?.data_entry_types.filter(
      (d) => d.needs_recalculation,
    ) ?? []
  );
}

async function confirmModuleRecalculation(): Promise<void> {
  const moduleTypeId = recalcDialogModuleTypeId.value;
  if (moduleTypeId === null) return;
  showRecalcDialog.value = false;
  recalcRunning.value[moduleTypeId] = true;
  try {
    const jobId =
      await backofficeDataManagement.initiateModuleEmissionRecalculation(
        moduleTypeId,
        props.selectedYear,
        recalcOnlyStale.value,
      );
    backofficeDataManagement.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        const result = payload?.result;
        if (result === IngestionResult.WARNING) {
          Notify.create({
            type: 'warning',
            message: $t('data_management_recalculation_warning'),
            caption: payload?.status_message ?? '',
            position: 'top',
            timeout: 5000,
          });
        } else if (result === IngestionResult.SUCCESS) {
          Notify.create({
            type: 'positive',
            message: $t('data_management_recalculation_success'),
            position: 'top',
            timeout: 5000,
          });
        } else {
          Notify.create({
            type: 'negative',
            message: $t('data_management_recalculation_error'),
            caption: payload?.status_message ?? '',
            position: 'top',
            timeout: 5000,
          });
        }
        recalcRunning.value[moduleTypeId] = false;
        void refreshRecalculationStatus();
      },
      (payload?: JobUpdatePayload) => {
        Notify.create({
          type: 'negative',
          message: $t('data_management_recalculation_error'),
          caption: payload?.status_message ?? '',
          position: 'top',
          timeout: 5000,
        });
        recalcRunning.value[moduleTypeId] = false;
        void refreshRecalculationStatus();
      },
      () => {
        recalcRunning.value[moduleTypeId] = false;
      },
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '';
    Notify.create({
      type: 'negative',
      message: $t('data_management_recalculation_error'),
      caption: msg,
      position: 'top',
    });
    recalcRunning.value[moduleTypeId] = false;
  }
}

async function triggerTypeRecalculation(
  sub: SubmoduleConfigItem,
): Promise<void> {
  if (sub.dataEntryTypeId === undefined) return;
  const key = `${sub.moduleTypeId}-${sub.dataEntryTypeId}`;
  recalcTypeRunning.value[key] = true;
  try {
    const jobId = await backofficeDataManagement.initiateEmissionRecalculation(
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
            message: $t('data_management_recalculation_warning'),
            caption: payload?.status_message ?? '',
            position: 'top',
            timeout: 5000,
          });
        } else if (result === IngestionResult.SUCCESS) {
          Notify.create({
            type: 'positive',
            message: $t('data_management_recalculation_success'),
            position: 'top',
            timeout: 5000,
          });
        } else {
          Notify.create({
            type: 'negative',
            message: $t('data_management_recalculation_error'),
            caption: payload?.status_message ?? '',
            position: 'top',
            timeout: 5000,
          });
        }
        recalcTypeRunning.value[key] = false;
        void refreshRecalculationStatus();
      },
      (payload?: JobUpdatePayload) => {
        Notify.create({
          type: 'negative',
          message: $t('data_management_recalculation_error'),
          caption: payload?.status_message ?? '',
          position: 'top',
          timeout: 5000,
        });
        recalcTypeRunning.value[key] = false;
        void refreshRecalculationStatus();
      },
      () => {
        recalcTypeRunning.value[key] = false;
      },
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : '';
    Notify.create({
      type: 'negative',
      message: $t('data_management_recalculation_error'),
      caption: msg,
      position: 'top',
    });
    recalcTypeRunning.value[key] = false;
  }
}

async function handleJobCompleted() {
  await yearConfigStore.fetchConfig(props.selectedYear);
  await refreshRecalculationStatus();
}

async function handleJobProgressing() {
  await yearConfigStore.fetchConfig(props.selectedYear);
}

// ── Provide to SubmoduleConfig ────────────────────────────────────────────────

provide('openDataEntryDialog', openDataEntryDialog);
provide('getRecalcStatus', getRecalcStatus);
provide('refreshRecalculationStatus', refreshRecalculationStatus);
provide('handleJobCompleted', handleJobCompleted);
provide('handleJobProgressing', handleJobProgressing);
provide('recalcTypeRunning', recalcTypeRunning);
provide('triggerTypeRecalculation', triggerTypeRecalculation);

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(() => {
  void refreshRecalculationStatus();
});

watch(
  () => props.selectedYear,
  () => {
    void refreshRecalculationStatus();
  },
);
</script>
<template>
  <q-card flat bordered class="q-pa-none q-mb-lg">
    <q-expansion-item v-model="expanded" expand-separator>
      <template #header>
        <q-item-section avatar>
          <ModuleIcon :name="module" size="md" color="accent" />
        </q-item-section>
        <q-item-section>
          <div class="row items-center q-gutter-sm">
            <span class="text-h4 text-weight-medium">{{ $t(module) }}</span>
            <q-badge
              v-if="!isModuleEnabled(module)"
              outline
              rounded
              color="grey"
              class="text-weight-medium"
              :label="$t('common_disabled')"
            />
            <q-badge
              v-else-if="isModuleIncomplete(module)"
              outline
              rounded
              color="accent"
              class="text-weight-medium"
              :label="$t('common_filter_incomplete')"
            />
            <q-badge
              v-if="
                recalculationStatus[getModuleTypeIdFromName(module)]
                  ?.needs_recalculation
              "
              outline
              rounded
              color="warning"
              class="text-weight-medium"
              :label="$t('data_management_recalculation_needed')"
            />
          </div>
        </q-item-section>
        <q-item-section side>
          <div class="row items-center q-gutter-sm">
            <q-spinner-rings
              v-if="recalcRunning[getModuleTypeIdFromName(module)]"
              color="grey"
              size="sm"
            />
            <q-btn
              v-if="
                recalculationStatus[getModuleTypeIdFromName(module)]
                  ?.needs_recalculation
              "
              flat
              dense
              size="sm"
              icon="refresh"
              color="accent"
              :label="$t('data_management_recalculate_emissions')"
              @click.stop="openRecalcDialog(getModuleTypeIdFromName(module))"
            />
          </div>
        </q-item-section>
      </template>
      <q-separator />
      <q-card flat class="q-pa-none row">
        <q-card flat class="col q-px-lg q-pt-xl q-pb-md border-right">
          <div class="row items-center q-mb-xs">
            <q-icon
              name="power_settings_new"
              color="accent"
              size="xs"
              class="q-mr-sm"
            />
            <div class="text-body1 text-weight-medium">
              {{ $t('data_management_module_activation_title') }}
            </div>
          </div>
          <div class="text-body2 text-secondary q-mb-sm">
            {{ $t('data_management_module_activation_description') }}
          </div>
          <q-toggle
            :model-value="isModuleEnabled(module)"
            color="accent"
            keep-color
            size="lg"
            @update:model-value="
              (val: boolean) => updateModuleEnabled(module, val)
            "
          />
        </q-card>
      </q-card>

      <div
        :style="
          !isModuleEnabled(module)
            ? 'opacity: 0.45; pointer-events: none'
            : undefined
        "
      >
        <q-separator class="q-my-xs" />
        <q-card flat class="q-pa-none row">
          <q-card flat class="col q-px-lg q-pt-xl q-pb-md border-right">
            <div class="row items-center q-mb-xs">
              <q-icon
                name="o_help_center"
                color="accent"
                size="xs"
                class="q-mr-sm"
              />
              <div class="text-body1 text-weight-medium">
                {{ $t('data_management_uncertainty_title') }}
              </div>
            </div>
            <div class="text-body2 text-secondary q-mb-sm">
              {{ $t('data_management_uncertainty_description') }}
            </div>
            <q-radio
              :model-value="getModuleUncertainty(module)"
              val="none"
              :label="$t('data_management_uncertainty_none')"
              color="accent"
              @update:model-value="updateModuleUncertainty(module, 'none')"
            />
            <q-radio
              :model-value="getModuleUncertainty(module)"
              val="low"
              :label="$t('data_management_uncertainty_low')"
              color="accent"
              @update:model-value="updateModuleUncertainty(module, 'low')"
            />
            <q-radio
              :model-value="getModuleUncertainty(module)"
              val="medium"
              :label="$t('data_management_uncertainty_medium')"
              color="accent"
              @update:model-value="updateModuleUncertainty(module, 'medium')"
            />
            <q-radio
              :model-value="getModuleUncertainty(module)"
              val="high"
              :label="$t('data_management_uncertainty_high')"
              color="accent"
              @update:model-value="updateModuleUncertainty(module, 'high')"
            />
          </q-card>
        </q-card>
        <q-separator
          v-if="
            (MODULE_COMMON_UPLOADS[module]?.length ?? 0) > 0 ||
            (MODULE_SUBMODULES[module] ?? []).length > 0
          "
          class="q-my-xs"
        />
        <!-- Common module-level uploads (equipment, purchase, external cloud) -->
        <template v-if="MODULE_COMMON_UPLOADS[module]?.length">
          <div
            v-for="common in MODULE_COMMON_UPLOADS[module]"
            :key="common.key"
            class="q-mx-lg q-pt-md"
          >
            <div
              v-if="common.headerIcon || common.descriptionKey"
              class="q-px-xs"
            >
              <div class="row items-center q-mb-xs">
                <q-icon
                  v-if="common.headerIcon"
                  :name="common.headerIcon"
                  color="accent"
                  size="xs"
                  class="q-mr-sm"
                />
                <div class="text-body1 text-weight-medium">
                  {{ $t(common.labelKey) }}
                </div>
              </div>
              <div
                v-if="common.descriptionKey"
                class="text-body2 text-secondary q-mb-sm"
              >
                {{ $t(common.descriptionKey) }}
              </div>
            </div>
            <div v-else class="text-body2 text-weight-medium q-mb-sm q-px-xs">
              {{ $t(common.labelKey) }}
            </div>
            <div class="row q-pb-md" style="gap: 1rem">
              <!-- Data -->
              <q-card
                v-if="getImportRow(common).hasData"
                flat
                class="col q-pa-lg"
                :style="cardStyle(dataButtonColor(getImportRow(common)))"
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
                      getImportRow(common).lastDataJob?.state ===
                      IngestionState.RUNNING
                    "
                    color="grey"
                  />
                  <q-btn
                    :color="dataButtonColor(getImportRow(common))"
                    icon="add"
                    size="sm"
                    :label="dataButtonLabel(getImportRow(common))"
                    class="text-weight-medium"
                    :disable="getImportRow(common).isDisabled"
                    @click="
                      openDataEntryDialog(
                        getImportRow(common),
                        TargetType.DATA_ENTRIES,
                      )
                    "
                  />
                  <!-- Per-type emission recalculation button -->
                  <template
                    v-if="
                      common.dataEntryTypeId !== undefined &&
                      getImportRow(common).hasFactors
                    "
                  >
                    <q-spinner-rings
                      v-if="
                        recalcTypeRunning[
                          `${common.moduleTypeId}-${common.dataEntryTypeId}`
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
                          getRecalcStatus(common)?.needs_recalculation
                            ? 'warning'
                            : undefined
                        "
                        size="sm"
                        :label="$t('data_management_recalculate_emissions')"
                        :title="
                          getRecalcStatus(common)?.needs_recalculation
                            ? $t('data_management_recalculation_needed')
                            : ''
                        "
                        class="text-weight-medium"
                        :disable="getImportRow(common).isDisabled"
                        @click="triggerTypeRecalculation(common)"
                      />
                    </template>
                  </template>
                </div>
              </q-card>

              <!-- Factors -->
              <q-card
                v-if="getImportRow(common).hasFactors"
                flat
                class="col q-pa-lg"
                :style="cardStyle(factorButtonColor(getImportRow(common)))"
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
                <div class="text-caption text-secondary q-mb-md">
                  {{ $t('data_management_factor_description') }}
                </div>
                <div class="row justify-between items-center full-width">
                  <div class="row items-center" style="gap: 0.5rem">
                    <q-spinner-rings
                      v-if="
                        getImportRow(common).lastFactorJob?.state ===
                        IngestionState.RUNNING
                      "
                      color="grey"
                    />
                    <q-btn
                      :color="factorButtonColor(getImportRow(common))"
                      icon="add"
                      size="sm"
                      :label="factorButtonLabel(getImportRow(common))"
                      class="text-weight-medium"
                      :disable="getImportRow(common).isDisabled"
                      @click="
                        openDataEntryDialog(
                          getImportRow(common),
                          TargetType.FACTORS,
                        )
                      "
                    />
                  </div>
                  <div
                    v-if="getImportRow(common).lastFactorJob?.meta"
                    class="row items-center no-wrap"
                    style="gap: 0.75rem"
                  >
                    <div class="column items-end">
                      <div
                        class="row items-center text-body2 text-weight-medium"
                      >
                        <span class="text-positive q-mr-xs">✓</span>
                        {{
                          safeFileName(getImportRow(common).lastFactorJob?.meta)
                        }}
                      </div>
                      <div class="text-caption text-grey-7">
                        {{
                          getImportRow(common).lastFactorJob?.meta
                            ?.rows_processed
                        }}
                        {{ $t('data_management_rows_imported') }}
                        <span
                          v-if="
                            getImportRow(common).lastFactorJob?.meta?.timestamp
                          "
                        >
                          •
                          {{
                            new Date(
                              getImportRow(common).lastFactorJob.meta
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
                        downloadLastCsv(
                          getImportRow(common),
                          TargetType.FACTORS,
                        )
                      "
                    >
                      <q-tooltip>{{
                        $t('data_management_download_last_csv')
                      }}</q-tooltip>
                    </q-btn>
                  </div>
                </div>
                <div
                  v-if="
                    getImportRow(common).lastFactorJob?.result ===
                      IngestionResult.WARNING ||
                    getImportRow(common).lastFactorJob?.result ===
                      IngestionResult.ERROR
                  "
                  class="q-mt-md q-pa-md bg-grey-2 rounded-borders"
                >
                  <div
                    class="text-body2 text-weight-bold q-mb-sm text-negative"
                  >
                    {{ getImportRow(common).lastFactorJob?.status_message }}
                  </div>
                  <div
                    v-if="
                      getImportRow(common).lastFactorJob?.meta?.error !==
                      getImportRow(common).lastFactorJob?.status_message
                    "
                    class="text-body2 q-mb-md"
                  >
                    {{ getImportRow(common).lastFactorJob?.meta?.error }}
                  </div>
                </div>
              </q-card>
            </div>
          </div>
          <q-separator
            v-if="(MODULE_SUBMODULES[module] ?? []).length > 0"
            class="q-my-xs"
          />
        </template>
        <template v-if="(MODULE_SUBMODULES[module] ?? []).length > 0">
          <div class="q-px-lg q-pt-md q-pb-sm">
            <div class="row items-center q-mb-xs">
              <q-icon
                name="o_view_cozy"
                color="accent"
                size="xs"
                class="q-mr-sm"
              />
              <div class="text-body1 text-weight-medium">
                {{ $t('data_management_submodules_configuration_title') }}
              </div>
            </div>
            <div class="text-body2 text-secondary">
              {{ $t('data_management_submodules_configuration_description') }}
            </div>
          </div>
          <div class="q-mx-lg q-mb-lg column q-gutter-y-sm">
            <SubmoduleConfig :module="module" :selected-year="selectedYear" />
          </div>
        </template>
      </div>
    </q-expansion-item>
  </q-card>

  <data-entry-dialog
    v-model="showDataEntryDialog"
    :row="dialogCurrentRow || ({} as ImportRow)"
    :year="selectedYear"
    :target-type="dialogTargetType ?? TargetType.DATA_ENTRIES"
    @completed="handleJobCompleted"
    @progressing="handleJobProgressing"
  />

  <!-- Emission recalculation dialog -->
  <q-dialog v-model="showRecalcDialog" persistent>
    <q-card style="min-width: 480px">
      <q-card-section class="row items-center q-pb-none">
        <q-icon name="refresh" color="accent" size="sm" class="q-mr-sm" />
        <div class="text-h6">
          {{ $t('data_management_recalculate_emissions_title') }}
        </div>
      </q-card-section>
      <q-card-section class="text-body2">
        {{ $t('data_management_recalculate_emissions_description') }}
      </q-card-section>
      <q-card-section v-if="recalcDialogModuleTypeId !== null">
        <q-radio
          v-model="recalcOnlyStale"
          :val="true"
          :label="$t('data_management_recalculate_only_stale')"
          color="accent"
        />
        <div class="text-caption text-grey-7 q-ml-md q-mt-xs">
          {{
            $t('data_management_stale_types', {
              count: staleTypesForModule(recalcDialogModuleTypeId).length,
            })
          }}
        </div>
        <q-radio
          v-model="recalcOnlyStale"
          :val="false"
          :label="$t('data_management_recalculate_all')"
          color="accent"
          class="q-mt-sm"
        />
      </q-card-section>
      <q-card-actions align="right">
        <q-btn
          flat
          :label="$t('common_cancel')"
          @click="showRecalcDialog = false"
        />
        <q-btn
          color="accent"
          unelevated
          :label="$t('common_confirm')"
          @click="confirmModuleRecalculation()"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>
