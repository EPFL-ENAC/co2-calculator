<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import DataEntryDialog from 'src/components/organisms/data-management/DataEntryDialog.vue';
import TempFilesBanner from 'src/components/organisms/data-management/TempFilesBanner.vue';
import { MODULES_LIST, MODULES } from 'src/constant/modules';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

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
  type ReductionObjectiveGoal,
} from 'src/stores/yearConfig';

import { Notify, Loading } from 'quasar';
import { useI18n } from 'vue-i18n';

// TODO: fix the available years dynamically
const MIN_YEARS = 2024;
const availableYears = ref<number[]>([]);
const currentYear = new Date().getFullYear();
if (currentYear > MIN_YEARS) {
  for (let year = MIN_YEARS; year < currentYear; year++) {
    availableYears.value.push(year);
  }
}
const selectedYear = ref<number>(
  availableYears.value[availableYears.value.length - 1],
);

const backofficeDataManagement = useBackofficeDataManagement();
const yearConfigStore = useYearConfigStore();
const { t: $t } = useI18n();

const fetchYearConfig = async () => {
  await yearConfigStore.fetchConfig(selectedYear.value);
};

watch(
  selectedYear,
  async () => {
    try {
      await fetchYearConfig();
      await refreshRecalculationStatus();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to load year data';
      Notify.create({ type: 'negative', message: msg });
    }
  },
  { immediate: true },
);

const handleCreateYear = async () => {
  try {
    await yearConfigStore.createConfig(selectedYear.value);
    Notify.create({
      type: 'positive',
      message: $t('data_management_year_created', { year: selectedYear.value }),
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    Notify.create({ type: 'negative', message: msg });
  }
};

const handleUnitSync = async () => {
  try {
    await backofficeDataManagement.syncUnitsFromAccred(selectedYear.value);

    Notify.create({
      type: 'info',
      message: $t('data_management_unit_sync_started'),
      caption: $t('data_management_unit_sync_started_caption'),
    });

    setTimeout(() => {
      Notify.create({
        type: 'positive',
        message: $t('data_management_unit_sync_success'),
        caption: $t('data_management_unit_sync_success_caption'),
      });
    }, 5000);
  } catch (error: unknown) {
    const errorMessage =
      error instanceof Error ? error.message : 'Unknown error';
    Notify.create({
      type: 'negative',
      message: $t('data_management_unit_sync_error'),
      caption: errorMessage || $t('data_management_unit_sync_error_caption'),
    });
  }
};

const expandedModules = ref<Record<string, boolean>>({});
const reductionObjectivesExpanded = ref(false);

/** Default empty goal for a slot. */
function emptyGoal(): ReductionObjectiveGoal {
  return {
    target_year: 0,
    reduction_percentage: 0,
    reference_year: 0,
  };
}

/** Local goals (3 fixed slots). Updated from store on config change. */
const localGoals = ref<ReductionObjectiveGoal[]>([
  emptyGoal(),
  emptyGoal(),
  emptyGoal(),
]);

const isSavingGoals = ref(false);

/** Sync store → local when config is fetched. Percentage is converted to 0–100 for display. */
watch(
  () => yearConfigStore.config?.config?.reduction_objectives?.goals,
  (storeGoals) => {
    if (!storeGoals) return;
    for (let i = 0; i < 3; i++) {
      if (storeGoals[i]) {
        localGoals.value[i] = {
          ...storeGoals[i],
          reduction_percentage: storeGoals[i].reduction_percentage * 100,
        };
      } else {
        localGoals.value[i] = emptyGoal();
      }
    }
  },
  { immediate: true },
);

/** True when at least one goal has meaningful data filled. */
const hasReductionGoals = computed(() =>
  localGoals.value.some((g) => g.target_year > 0 && g.reference_year > 0),
);

/** True when all filled-in goals pass validation (percentage displayed as 0–100). */
const goalsAreValid = computed(() =>
  localGoals.value.every((g) => {
    const isEmpty =
      !g.target_year && !g.reference_year && !g.reduction_percentage;
    if (isEmpty) return true;
    return (
      g.target_year > selectedYear.value &&
      g.reduction_percentage >= 0 &&
      g.reduction_percentage <= 100 &&
      g.reference_year > 0
    );
  }),
);

/** Persist all non-empty goals to the store. Converts percentage from 0–100 display to 0–1 storage. */
async function saveReductionGoals(): Promise<void> {
  const goalsToSave = localGoals.value
    .filter((g) => g.target_year > 0 && g.reference_year > 0)
    .map((g) => ({
      ...g,
      reduction_percentage: g.reduction_percentage / 100,
    }));

  isSavingGoals.value = true;
  try {
    await yearConfigStore.updateConfig(selectedYear.value, {
      config: {
        reduction_objectives: { goals: goalsToSave },
      },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  } finally {
    isSavingGoals.value = false;
  }
}

/** File refs for reduction objective CSV uploads. */
const footprintFile = ref<File | null>(null);
const populationFile = ref<File | null>(null);
const scenariosFile = ref<File | null>(null);

/** Uploaded file names derived from the store. */
const uploadedFileNames = computed(() => {
  const files = yearConfigStore.config?.config?.reduction_objectives?.files;
  return {
    footprint: files?.institutional_footprint?.filename ?? null,
    population: files?.population_projections?.filename ?? null,
    scenarios: files?.unit_scenarios?.filename ?? null,
  };
});

/** Handle a reduction-objective file upload. */
async function handleReductionFileUpload(
  category: 'footprint' | 'population' | 'scenarios',
  file: File | null,
): Promise<void> {
  if (!file) return;
  Loading.show({ message: $t('uploading_file') });
  try {
    await yearConfigStore.uploadFile(selectedYear.value, category, file);
    if (category === 'footprint') footprintFile.value = null;
    if (category === 'population') populationFile.value = null;
    if (category === 'scenarios') scenariosFile.value = null;
    Notify.create({ type: 'positive', message: $t('file_upload_success') });
  } catch {
    Notify.create({ type: 'negative', message: $t('file_upload_error') });
  } finally {
    Loading.hide();
  }
}

type SubmoduleConfig = {
  key: string;
  labelKey: string;
  moduleTypeId: number;
  dataEntryTypeId?: number;
  noData?: true;
  noFactors?: true;
  hasApi?: true;
  other?: string;
  isDisabled?: true;
};

const MODULE_SUBMODULES: Partial<
  Record<(typeof MODULES)[keyof typeof MODULES], SubmoduleConfig[]>
> = {
  [MODULES.Headcount]: [
    {
      key: 'member',
      labelKey: `${MODULES.Headcount}-member`,
      moduleTypeId: 1,
      dataEntryTypeId: 1,
    },
    {
      key: 'student',
      labelKey: `${MODULES.Headcount}-student`,
      moduleTypeId: 1,
      dataEntryTypeId: 2,
      noData: true,
    },
  ],
  [MODULES.ProfessionalTravel]: [
    {
      key: 'train',
      labelKey: `${MODULES.ProfessionalTravel}-train`,
      moduleTypeId: 2,
      dataEntryTypeId: 21,
      other: 'data_management_other_train_stations',
    },
    {
      key: 'plane',
      labelKey: `${MODULES.ProfessionalTravel}-plane`,
      moduleTypeId: 2,
      dataEntryTypeId: 20,
      hasApi: true,
      other: 'data_management_other_airports',
    },
  ],
  [MODULES.Buildings]: [
    {
      key: 'building',
      labelKey: `${MODULES.Buildings}-rooms`,
      moduleTypeId: 3,
      dataEntryTypeId: 30,
      other: 'data_management_other_institution_rooms',
    },
    {
      key: 'energy_combustion',
      labelKey: `${MODULES.Buildings}-combustion`,
      moduleTypeId: 3,
      dataEntryTypeId: 31,
    },
  ],
  [MODULES.ProcessEmissions]: [
    {
      key: 'process_emissions',
      labelKey: 'data_management_submodule_process_emissions',
      moduleTypeId: 8,
      dataEntryTypeId: 50,
    },
  ],
  [MODULES.EquipmentElectricConsumption]: [
    {
      key: 'scientific',
      labelKey: `${MODULES.EquipmentElectricConsumption}-scientific`,
      moduleTypeId: 4,
    },
    {
      key: 'it',
      labelKey: `${MODULES.EquipmentElectricConsumption}-it`,
      moduleTypeId: 4,
    },
    {
      key: 'other',
      labelKey: `${MODULES.EquipmentElectricConsumption}-other`,
      moduleTypeId: 4,
    },
  ],
  [MODULES.Purchase]: [
    {
      key: 'scientific_equipment',
      labelKey: 'data_management_submodule_scientific_equipment',
      moduleTypeId: 5,
    },
    {
      key: 'it_equipment',
      labelKey: 'data_management_submodule_it_equipment',
      moduleTypeId: 5,
    },
    {
      key: 'consumable_accessories',
      labelKey: 'data_management_submodule_consumables_accessories',
      moduleTypeId: 5,
    },
    {
      key: 'biological_chemical_gaseous_product',
      labelKey: 'data_management_submodule_bio_chemical_gaseous',
      moduleTypeId: 5,
    },
    {
      key: 'services',
      labelKey: 'data_management_submodule_services',
      moduleTypeId: 5,
    },
    {
      key: 'vehicles',
      labelKey: 'data_management_submodule_vehicles',
      moduleTypeId: 5,
    },
    {
      key: 'other_purchases',
      labelKey: 'data_management_submodule_other_purchases',
      moduleTypeId: 5,
    },
    {
      key: 'additional_purchases',
      labelKey: 'data_management_submodule_additional_purchases',
      moduleTypeId: 5,
      dataEntryTypeId: 67,
    },
  ],
  [MODULES.ResearchFacilities]: [
    {
      key: 'research-facilities',
      labelKey: 'data_management_submodule_research_facilities',
      moduleTypeId: 6,
      dataEntryTypeId: 70,
    },
    {
      key: 'mice_and_fish_animal_facilities',
      labelKey: 'data_management_submodule_animal_facilities',
      moduleTypeId: 6,
      dataEntryTypeId: 71,
    },
  ],
  [MODULES.ExternalCloudAndAI]: [
    {
      key: 'external_clouds',
      labelKey: `${MODULES.ExternalCloudAndAI}.cloud-services`,
      moduleTypeId: 7,
      dataEntryTypeId: 40,
    },
    {
      key: 'external_ai',
      labelKey: `${MODULES.ExternalCloudAndAI}.ai-services`,
      moduleTypeId: 7,
      dataEntryTypeId: 41,
    },
  ],
};

// ── Helpers mirroring AnnualDataImport ───────────────────────────────────────

function findJob(
  jobs: SyncJobSummary[],
  moduleTypeId: number,
  targetType: TargetType | null,
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

const QUASAR_COLOR_MAP: Record<string, string> = {
  accent: 'var(--q-accent)',
  positive: 'var(--q-positive)',
  negative: 'var(--q-negative)',
  warning: 'var(--q-warning)',
  'grey-4': '#bdbdbd',
};

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

const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

function openDataEntryDialog(row: ImportRow, targetType: TargetType | null) {
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
}

// ── Computed Factor Sync (Research Facilities only) ───────────────────────────

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
      selectedYear.value,
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

/**
 * Safely extract the filename from a job meta object that may be unknown.
 * Returns undefined when not available.
 */
function safeFileName(meta: unknown): string | undefined {
  const fp = (meta as Record<string, unknown>)?.file_path as string | undefined;
  if (!fp) return undefined;
  const parts = fp.split('/');
  return parts.length ? parts[parts.length - 1] : fp;
}

const jobsRefreshKey = ref(0);

// ── Recalculation status ─────────────────────────────────────────────────────

/** Map from module_type_id to its full recalculation status. */
const recalculationStatus = ref<Record<number, ModuleRecalculationStatus>>({});

/** Fetch (or refresh) recalculation status for the selected year. */
async function refreshRecalculationStatus(): Promise<void> {
  const statuses = await backofficeDataManagement.fetchRecalculationStatus(
    selectedYear.value,
  );
  const map: Record<number, ModuleRecalculationStatus> = {};
  for (const s of statuses) {
    map[s.module_type_id] = s;
  }
  recalculationStatus.value = map;
}

/** Return the per-type recalculation row for a submodule, if any. */
function getRecalcStatus(
  sub: SubmoduleConfig,
): RecalculationStatus | undefined {
  if (sub.dataEntryTypeId === undefined) return undefined;
  const moduleStatus = recalculationStatus.value[sub.moduleTypeId];
  return moduleStatus?.data_entry_types.find(
    (d) => d.data_entry_type_id === sub.dataEntryTypeId,
  );
}

// ── Module-level recalculation dialog ────────────────────────────────────────

const showRecalcDialog = ref(false);
const recalcDialogModuleTypeId = ref<number | null>(null);
const recalcOnlyStale = ref(true);
const recalcRunning = ref<Record<number, boolean>>({});
const recalcTypeRunning = ref<Record<string, boolean>>({});

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
        selectedYear.value,
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

async function triggerTypeRecalculation(sub: SubmoduleConfig): Promise<void> {
  if (sub.dataEntryTypeId === undefined) return;
  const key = `${sub.moduleTypeId}-${sub.dataEntryTypeId}`;
  recalcTypeRunning.value[key] = true;
  try {
    const jobId = await backofficeDataManagement.initiateEmissionRecalculation(
      sub.moduleTypeId,
      sub.dataEntryTypeId,
      selectedYear.value,
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
  await yearConfigStore.fetchConfig(selectedYear.value);
  await refreshRecalculationStatus();
  jobsRefreshKey.value += 1;
}

async function handleJobProgressing() {
  await yearConfigStore.fetchConfig(selectedYear.value);
  jobsRefreshKey.value += 1;
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

/**
 * Get the module-level enabled flag from the year config store.
 */
function isModuleEnabled(module: string): boolean {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return true;
  const moduleConfig =
    yearConfigStore.config?.config?.modules?.[String(moduleTypeId)];
  return moduleConfig?.enabled ?? true;
}

/**
 * Toggle module enabled state and persist via PATCH.
 */
async function updateModuleEnabled(
  module: string,
  value: boolean,
): Promise<void> {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return;
  const moduleKey = String(moduleTypeId);

  try {
    await yearConfigStore.updateConfig(selectedYear.value, {
      config: { modules: { [moduleKey]: { enabled: value } } },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  }
}

/**
 * Get the submodule-level enabled flag from the year config store.
 */
function isSubmoduleEnabled(sub: SubmoduleConfig): boolean {
  const moduleKey = String(sub.moduleTypeId);
  const subKey =
    sub.dataEntryTypeId !== undefined ? String(sub.dataEntryTypeId) : undefined;
  if (!subKey) return true;
  const moduleConfig = yearConfigStore.config?.config?.modules?.[moduleKey];
  return moduleConfig?.submodules?.[subKey]?.enabled ?? true;
}

/**
 * Toggle submodule enabled state and persist via PATCH.
 */
async function updateSubmoduleEnabled(
  sub: SubmoduleConfig,
  value: boolean,
): Promise<void> {
  const moduleKey = String(sub.moduleTypeId);
  const subKey =
    sub.dataEntryTypeId !== undefined ? String(sub.dataEntryTypeId) : undefined;
  if (!subKey) return;

  try {
    await yearConfigStore.updateConfig(selectedYear.value, {
      config: {
        modules: {
          [moduleKey]: {
            submodules: { [subKey]: { enabled: value } },
          },
        },
      },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  }
}

type UncertaintyTag = 'none' | 'low' | 'medium' | 'high';

/**
 * Resolve the module type ID from its name via MODULE_SUBMODULES.
 */
function getModuleTypeIdFromName(module: string): number {
  const subs =
    MODULE_SUBMODULES[module as keyof typeof MODULE_SUBMODULES] ?? [];
  return subs.length > 0 ? subs[0].moduleTypeId : 0;
}

/**
 * Get the current uncertainty tag for a module from the year config store.
 */
function getModuleUncertainty(module: string): UncertaintyTag {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return 'medium';
  const moduleConfig =
    yearConfigStore.config?.config?.modules?.[String(moduleTypeId)];
  return moduleConfig?.uncertainty_tag ?? 'medium';
}

/**
 * Update uncertainty tag for a module and persist via PATCH.
 */
async function updateModuleUncertainty(
  module: string,
  value: UncertaintyTag,
): Promise<void> {
  const moduleTypeId = getModuleTypeIdFromName(module);
  if (!moduleTypeId) return;
  const moduleKey = String(moduleTypeId);

  try {
    await yearConfigStore.updateConfig(selectedYear.value, {
      config: {
        modules: {
          [moduleKey]: {
            uncertainty_tag: value,
          },
        },
      },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  }
}

/**
 * Get the current threshold value for a submodule from the year config store.
 */
function getSubmoduleThreshold(sub: SubmoduleConfig): number | null {
  const moduleKey = String(sub.moduleTypeId);
  const subKey =
    sub.dataEntryTypeId !== undefined ? String(sub.dataEntryTypeId) : undefined;
  if (!subKey) return null;
  const moduleConfig = yearConfigStore.config?.config?.modules?.[moduleKey];
  if (!moduleConfig) return null;
  return moduleConfig.submodules?.[subKey]?.threshold ?? null;
}

/**
 * Update threshold for a submodule and persist via PATCH.
 */
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
    await yearConfigStore.updateConfig(selectedYear.value, {
      config: {
        modules: {
          [moduleKey]: {
            ...existingModule,
            submodules: {
              ...existingModule.submodules,
              [subKey]: {
                ...existingSub,
                threshold: value,
              },
            },
          },
        },
      },
    });
    Notify.create({
      type: 'positive',
      message: $t('year_config_saved'),
    });
  } catch {
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  }
}

watch(
  () => yearConfigStore.loading,
  (newValue) => {
    if (newValue) {
      Loading.show({ message: $t('data_management_loading') });
    } else {
      Loading.hide();
    }
  },
);

onMounted(() => {
  // Loading.show({
  //   message: $t('data_management_loading'),
  // });
});
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />
    <div class="q-my-xl q-px-xl">
      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="row justify-between items-center">
          <q-card-section class="row justify-between full-width q-pa-none">
            <div class="text-subtitle1">
              {{ $t('data_management_reporting_year') }}
            </div>
            <q-btn
              color="accent"
              :label="$t('data_management_sync_units_from_accred')"
              icon="sync"
              size="sm"
              :loading="backofficeDataManagement.loading"
              :disable="backofficeDataManagement.loading"
              @click="handleUnitSync"
            >
            </q-btn>
          </q-card-section>

          <q-select
            v-model="selectedYear"
            :options="availableYears"
            outlined
            dense
            class="full-width q-my-md"
          >
            <template #prepend>
              <q-icon name="event" color="accent" size="xs" />
            </template>
          </q-select>

          <div class="text-body2 text-secondary">
            {{ $t('data_management_reporting_year_hint') }}
          </div>
        </div>
      </q-card>
      <!-- Startup: no configuration exists yet -->
      <q-card
        v-if="yearConfigStore.notFound && !yearConfigStore.loading"
        flat
        bordered
        class="q-pa-xl q-mb-xl text-center"
      >
        <q-icon
          name="calendar_today"
          size="64px"
          color="grey-5"
          class="q-mb-md"
        />
        <div class="text-h6 q-mb-sm">
          {{
            $t('data_management_year_not_configured', { year: selectedYear })
          }}
        </div>
        <div class="text-body2 text-secondary q-mb-lg">
          {{ $t('data_management_year_not_configured_hint') }}
        </div>
        <q-btn
          color="primary"
          icon="add"
          :label="$t('data_management_create_year', { year: selectedYear })"
          :loading="yearConfigStore.loading"
          @click="handleCreateYear"
        />
      </q-card>
      <!-- Loading skeleton -->
      <template v-else-if="yearConfigStore.loading">
        <q-skeleton type="rect" height="80px" class="q-mb-md" />
        <q-skeleton type="rect" height="200px" class="q-mb-md" />
      </template>
      <template v-if="yearConfigStore.config && !yearConfigStore.loading">
        <temp-files-banner class="q-mb-xl" />
        <template v-for="module in MODULES_LIST" :key="module">
          <q-card flat bordered class="q-pa-none q-mb-lg">
            <q-expansion-item
              v-model="expandedModules[module]"
              expand-separator
            >
              <template #header>
                <q-item-section avatar>
                  <ModuleIcon :name="module" size="md" color="accent" />
                </q-item-section>
                <q-item-section>
                  <div class="row items-center q-gutter-sm">
                    <span class="text-h4 text-weight-medium">{{
                      $t(module)
                    }}</span>
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
                      @click.stop="
                        openRecalcDialog(getModuleTypeIdFromName(module))
                      "
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
                    @update:model-value="
                      updateModuleUncertainty(module, 'none')
                    "
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
                    @update:model-value="
                      updateModuleUncertainty(module, 'medium')
                    "
                  />
                  <q-radio
                    :model-value="getModuleUncertainty(module)"
                    val="high"
                    :label="$t('data_management_uncertainty_high')"
                    color="accent"
                    @update:model-value="
                      updateModuleUncertainty(module, 'high')
                    "
                  />
                </q-card>
              </q-card>
              <q-separator class="q-my-xs" />
              <q-card flat class="q-pa-none row">
                <q-card flat class="col q-px-lg q-pt-xl q-pb-md border-right">
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
                    {{
                      $t('data_management_submodules_configuration_description')
                    }}
                  </div>
                </q-card>
              </q-card>
              <div class="q-mx-lg q-mt-md q-mb-lg">
                <q-card
                  v-for="submodule in MODULE_SUBMODULES[module] ?? []"
                  :key="submodule.key"
                  flat
                  bordered
                  class="q-mb-md"
                >
                  <q-expansion-item expand-separator>
                    <template #header>
                      <q-item-section>
                        <div class="row items-center q-gutter-sm">
                          <span class="text-body2 text-weight-medium">{{
                            $t(submodule.labelKey)
                          }}</span>
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
                        </div>
                      </q-item-section>
                    </template>
                    <q-separator class="q-mb-xs" />
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
                        {{
                          $t('data_management_submodule_activation_description')
                        }}
                      </div>
                      <q-toggle
                        :model-value="isSubmoduleEnabled(submodule)"
                        color="accent"
                        keep-color
                        size="md"
                        @update:model-value="
                          (val: boolean) =>
                            updateSubmoduleEnabled(submodule, val)
                        "
                      />
                    </q-card>
                    <q-separator class="q-my-xs" />
                    <q-card flat class="col q-px-lg q-pt-lg q-pb-md">
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
                    <q-separator class="q-my-xs" />
                    <div class="row q-pa-md" style="gap: 1rem">
                      <!-- Data -->
                      <q-card
                        v-if="getImportRow(submodule).hasData"
                        flat
                        class="col q-pa-lg"
                        :style="
                          cardStyle(dataButtonColor(getImportRow(submodule)))
                        "
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
                                  getRecalcStatus(submodule)
                                    ?.needs_recalculation
                                    ? 'warning'
                                    : undefined
                                "
                                size="sm"
                                :label="
                                  $t('data_management_recalculate_emissions')
                                "
                                :title="
                                  getRecalcStatus(submodule)
                                    ?.needs_recalculation
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
                        :style="
                          cardStyle(factorButtonColor(getImportRow(submodule)))
                        "
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
                          {{
                            $t('data_management_factor_headcount_description')
                          }}
                        </div>
                        <div v-else class="text-caption text-secondary q-mb-md">
                          {{ $t('data_management_factor_description') }}
                        </div>
                        <div
                          class="row justify-between items-center full-width"
                        >
                          <div class="row items-center" style="gap: 0.5rem">
                            <q-spinner-rings
                              v-if="
                                getImportRow(submodule).lastFactorJob?.state ===
                                IngestionState.RUNNING
                              "
                              color="grey"
                            />
                            <q-btn
                              :color="
                                factorButtonColor(getImportRow(submodule))
                              "
                              icon="add"
                              size="sm"
                              :label="
                                factorButtonLabel(getImportRow(submodule))
                              "
                              class="text-weight-medium"
                              :disable="getImportRow(submodule).isDisabled"
                              @click="
                                openDataEntryDialog(
                                  getImportRow(submodule),
                                  TargetType.FACTORS,
                                )
                              "
                            />
                            <template
                              v-if="module === MODULES.ResearchFacilities"
                            >
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
                                  getImportRow(submodule).isDisabled ||
                                  anyComputedFactorRunning
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
                              <div
                                class="row items-center text-body2 text-weight-medium"
                              >
                                <span class="text-positive q-mr-xs">✓</span>
                                {{
                                  safeFileName(
                                    getImportRow(submodule).lastFactorJob?.meta,
                                  )
                                }}
                              </div>
                              <div class="text-caption text-grey-7">
                                {{
                                  getImportRow(submodule).lastFactorJob?.meta
                                    ?.rows_processed
                                }}
                                {{ $t('data_management_rows_imported') }}
                                <span
                                  v-if="
                                    getImportRow(submodule).lastFactorJob?.meta
                                      ?.timestamp
                                  "
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
                                downloadLastCsv(
                                  getImportRow(submodule),
                                  TargetType.FACTORS,
                                )
                              "
                            >
                              <q-tooltip>{{
                                $t('data_management_download_last_csv')
                              }}</q-tooltip>
                            </q-btn>
                            <q-icon
                              v-if="
                                getImportRow(submodule).lastFactorJob
                                  ?.result === IngestionResult.WARNING ||
                                getImportRow(submodule).lastFactorJob
                                  ?.result === IngestionResult.ERROR
                              "
                              name="info"
                              size="sm"
                              class="cursor-pointer"
                            >
                              <q-tooltip>
                                <div class="text-left">
                                  {{
                                    getImportRow(submodule).lastFactorJob
                                      ?.status_message
                                  }}:
                                  <span
                                    v-if="
                                      getImportRow(submodule).lastFactorJob
                                        ?.meta?.error !==
                                      getImportRow(submodule).lastFactorJob
                                        ?.status_message
                                    "
                                    class="text-negative"
                                  >
                                    {{
                                      getImportRow(submodule).lastFactorJob
                                        ?.meta?.error || ''
                                    }}
                                  </span>
                                  <hr />
                                  <div
                                    v-for="(key, value, index) in getImportRow(
                                      submodule,
                                    ).lastFactorJob?.meta?.stats || []"
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
                          <div
                            class="text-body2 text-weight-bold q-mb-sm text-negative"
                          >
                            {{
                              getImportRow(submodule).lastFactorJob
                                ?.status_message
                            }}
                          </div>
                          <div
                            v-if="
                              getImportRow(submodule).lastFactorJob?.meta
                                ?.error !==
                              getImportRow(submodule).lastFactorJob
                                ?.status_message
                            "
                            class="text-body2 q-mb-md"
                          >
                            {{
                              getImportRow(submodule).lastFactorJob?.meta?.error
                            }}
                          </div>
                          <div
                            v-for="(key, value, index) in getImportRow(
                              submodule,
                            ).lastFactorJob?.meta?.stats || []"
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
                </q-card>
              </div>
            </q-expansion-item>
          </q-card>
        </template>

        <q-card flat bordered class="q-py-none q-mb-lg">
          <q-expansion-item
            v-model="reductionObjectivesExpanded"
            expand-separator
          >
            <template #header>
              <q-item-section avatar>
                <ModuleIcon
                  name="reduction-objectives"
                  size="md"
                  color="accent"
                />
              </q-item-section>
              <q-item-section>
                <div class="row items-center q-gutter-sm">
                  <span class="text-h4 text-weight-medium">
                    {{ $t('data_management_reduction_objectives') }}</span
                  >
                  <q-badge
                    v-if="!hasReductionGoals"
                    outline
                    rounded
                    color="accent"
                    class="text-weight-medium"
                    :label="$t('common_filter_incomplete')"
                  />
                </div>
              </q-item-section>
              <q-item-section class="text-h4 text-weight-medium">
              </q-item-section>
            </template>
            <q-separator />
            <!-- File Upload Section -->
            <q-card flat class="q-pa-none row">
              <q-card
                flat
                class="col q-px-lg q-py-xl"
                style="border-right: 1px solid #d5d5d5"
              >
                <div class="row items-start align-center q-my-xs">
                  <q-icon
                    name="barefoot"
                    color="accent"
                    size="xs"
                    class="q-mr-sm"
                  />
                  <div class="text-body1 text-weight-medium">
                    {{
                      $t('data_management_institution_carbon_footprint_title')
                    }}
                  </div>
                </div>
                <div class="text-body2 text-secondary">
                  {{
                    $t(
                      'data_management_institution_carbon_footprint_description',
                    )
                  }}
                </div>
                <div
                  v-if="uploadedFileNames.footprint"
                  class="text-caption text-positive q-mt-sm"
                >
                  <q-icon name="check" /> {{ uploadedFileNames.footprint }}
                </div>
                <div class="row q-gutter-md q-mt-lg">
                  <q-file
                    v-model="footprintFile"
                    outlined
                    dense
                    accept=".csv"
                    :label="$t('common_upload_csv')"
                    class="col"
                    @update:model-value="
                      handleReductionFileUpload('footprint', $event)
                    "
                  >
                    <template #prepend>
                      <q-icon name="o_upload" />
                    </template>
                  </q-file>
                </div>
              </q-card>
              <q-card
                flat
                class="col q-px-lg q-py-xl"
                style="border-right: 1px solid #d5d5d5"
              >
                <div class="row items-start align-center q-mb-xs">
                  <q-icon
                    name="o_groups_2"
                    color="accent"
                    size="xs"
                    class="q-mr-sm"
                  />
                  <div class="text-body1 text-weight-medium">
                    {{ $t('data_management_population_projections_title') }}
                  </div>
                </div>
                <div class="text-body2 text-secondary">
                  {{ $t('data_management_population_projections_description') }}
                </div>
                <div
                  v-if="uploadedFileNames.population"
                  class="text-caption text-positive q-mt-sm"
                >
                  <q-icon name="check" /> {{ uploadedFileNames.population }}
                </div>
                <div class="row q-gutter-md q-mt-lg">
                  <q-file
                    v-model="populationFile"
                    outlined
                    dense
                    accept=".csv"
                    :label="$t('common_upload_csv')"
                    class="col"
                    @update:model-value="
                      handleReductionFileUpload('population', $event)
                    "
                  >
                    <template #prepend>
                      <q-icon name="o_upload" />
                    </template>
                  </q-file>
                </div>
              </q-card>
              <q-card flat class="col q-px-lg q-py-xl border-right">
                <div class="row items-start align-center q-mb-xs">
                  <q-icon
                    name="o_square_foot"
                    color="accent"
                    size="xs"
                    class="q-mr-sm"
                  />
                  <div class="text-body1 text-weight-medium">
                    {{ $t('data_management_unit_reduction_scenarios_title') }}
                  </div>
                </div>
                <div class="text-body2 text-secondary">
                  {{
                    $t('data_management_unit_reduction_scenarios_description')
                  }}
                </div>
                <div
                  v-if="uploadedFileNames.scenarios"
                  class="text-caption text-positive q-mt-sm"
                >
                  <q-icon name="check" /> {{ uploadedFileNames.scenarios }}
                </div>
                <div class="row q-gutter-md q-mt-lg">
                  <q-file
                    v-model="scenariosFile"
                    outlined
                    dense
                    accept=".csv"
                    :label="$t('common_upload_csv')"
                    class="col"
                    @update:model-value="
                      handleReductionFileUpload('scenarios', $event)
                    "
                  >
                    <template #prepend>
                      <q-icon name="o_upload" />
                    </template>
                  </q-file>
                </div>
              </q-card>
            </q-card>
            <q-separator />
            <!-- Goals Section -->
            <q-item-section class="q-pt-xl q-pb-sm q-px-md">
              <div class="row items-start align-center q-mb-xs">
                <q-icon
                  name="adjust"
                  color="accent"
                  size="xs"
                  class="q-mr-sm"
                />
                <div class="text-body1 text-weight-medium">
                  {{ $t('data_management_define_reduction_objectives_title') }}
                </div>
              </div>
              <div class="text-body2 text-secondary">
                {{
                  $t('data_management_define_reduction_objectives_description')
                }}
              </div>
            </q-item-section>
            <div class="row q-my-sm">
              <!-- First Goal (mandatory) -->
              <q-card flat bordered class="q-pa-md q-ma-md col">
                <div class="row justify-between items-center">
                  <div class="text-body2 text-weight-medium">
                    {{ $t('data_management_first_reduction_objectives') }}
                  </div>
                  <div class="text-body2 text-secondary">
                    <span class="text-negative">*</span
                    >{{ $t('common_mandatory') }}
                  </div>
                </div>
                <div class="col full-width q-mt-lg q-gutter-md">
                  <q-input
                    v-model.number="localGoals[0].target_year"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t(
                        'data_management_first_reduction_objectives_target_year',
                      )
                    "
                    placeholder="2030"
                    :rules="[
                      (v: number) =>
                        !v ||
                        v > selectedYear ||
                        $t('year_config_target_year_error'),
                    ]"
                  />
                  <q-input
                    v-model.number="localGoals[0].reduction_percentage"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t('data_management_reduction_objectives_reduction_goal')
                    "
                    placeholder="40"
                    hint="0 – 100"
                    :rules="[
                      (v: number) =>
                        (!v && v !== undefined) ||
                        (v >= 0 && v <= 100) ||
                        $t('year_config_percentage_error'),
                    ]"
                  />
                  <q-input
                    v-model.number="localGoals[0].reference_year"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t('data_management_reduction_objectives_reference_year')
                    "
                    placeholder="2019"
                    :rules="[
                      (v: number) =>
                        !v || v > 0 || $t('year_config_reference_year_error'),
                    ]"
                  />
                </div>
              </q-card>
              <!-- Second Goal -->
              <q-card flat bordered class="q-pa-md q-ma-md col">
                <div class="text-body2 text-weight-medium">
                  {{ $t('data_management_second_reduction_objectives') }}
                </div>
                <div class="col full-width q-mt-lg q-gutter-md">
                  <q-input
                    v-model.number="localGoals[1].target_year"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t(
                        'data_management_first_reduction_objectives_target_year',
                      )
                    "
                    placeholder="2030"
                    :rules="[
                      (v: number) =>
                        !v ||
                        v > selectedYear ||
                        $t('year_config_target_year_error'),
                    ]"
                  />
                  <q-input
                    v-model.number="localGoals[1].reduction_percentage"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t('data_management_reduction_objectives_reduction_goal')
                    "
                    placeholder="40"
                    hint="0 – 100"
                    :rules="[
                      (v: number) =>
                        (!v && v !== undefined) ||
                        (v >= 0 && v <= 100) ||
                        $t('year_config_percentage_error'),
                    ]"
                  />
                  <q-input
                    v-model.number="localGoals[1].reference_year"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t('data_management_reduction_objectives_reference_year')
                    "
                    placeholder="2019"
                    :rules="[
                      (v: number) =>
                        !v || v > 0 || $t('year_config_reference_year_error'),
                    ]"
                  />
                </div>
              </q-card>
              <!-- Third Goal -->
              <q-card flat bordered class="q-pa-md q-ma-md col">
                <div class="text-body2 text-weight-medium">
                  {{ $t('data_management_third_reduction_objectives') }}
                </div>
                <div class="col full-width q-mt-lg q-gutter-md">
                  <q-input
                    v-model.number="localGoals[2].target_year"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t(
                        'data_management_first_reduction_objectives_target_year',
                      )
                    "
                    placeholder="2030"
                    :rules="[
                      (v: number) =>
                        !v ||
                        v > selectedYear ||
                        $t('year_config_target_year_error'),
                    ]"
                  />
                  <q-input
                    v-model.number="localGoals[2].reduction_percentage"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t('data_management_reduction_objectives_reduction_goal')
                    "
                    placeholder="40"
                    hint="0 – 100"
                    :rules="[
                      (v: number) =>
                        (!v && v !== undefined) ||
                        (v >= 0 && v <= 100) ||
                        $t('year_config_percentage_error'),
                    ]"
                  />
                  <q-input
                    v-model.number="localGoals[2].reference_year"
                    outlined
                    dense
                    type="number"
                    class="full-width"
                    :label="
                      $t('data_management_reduction_objectives_reference_year')
                    "
                    placeholder="2019"
                    :rules="[
                      (v: number) =>
                        !v || v > 0 || $t('year_config_reference_year_error'),
                    ]"
                  />
                </div>
              </q-card>
            </div>
            <q-btn
              color="accent"
              size="md"
              :label="$t('common_save')"
              :loading="isSavingGoals"
              :disable="!goalsAreValid"
              class="q-mb-md q-ml-md text-weight-medium text-capitalize"
              @click="saveReductionGoals"
            />
          </q-expansion-item>
        </q-card>
      </template>
    </div>
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
  </q-page>
</template>
