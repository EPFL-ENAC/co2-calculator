import { computed, ref } from 'vue';
import {
  useBackofficeDataManagement,
  IngestionState,
  IngestionResult,
  IngestionMethod,
  TargetType,
  type ImportRow,
  type SyncJobResponse,
  type JobUpdatePayload,
} from 'src/stores/backofficeDataManagement';
import { useYearConfigStore, type SyncJobSummary } from 'src/stores/yearConfig';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import type { SubmoduleConfig } from 'src/constant/backoffice-module-config';

export function useSubmoduleConfig() {
  const { t: $t } = useI18n();
  const yearConfigStore = useYearConfigStore();
  const backofficeDataManagement = useBackofficeDataManagement();
  const {
    isSubmoduleEnabled,
    isSubmoduleInputsDeactivated,
    isSubmoduleCsvDeactivated,
    getModule,
    getModuleNameFromSubmodule,
  } = yearConfigStore;

  /**
   * Issue #1215 — read the backend-computed flag from the enriched
   * submodule dict. Common-uploads (no ``dataEntryTypeId``) inherit
   * their module-level rollup since they have no per-submodule entry.
   */
  function isSubmoduleIncomplete(sub: SubmoduleConfig): boolean {
    const mod =
      yearConfigStore.config?.config?.modules?.[String(sub.moduleTypeId)];
    if (sub.dataEntryTypeId === undefined) {
      return !!mod?.incomplete;
    }
    return !!mod?.submodules?.[String(sub.dataEntryTypeId)]?.incomplete;
  }

  function toSyncJobResponse(
    job?: SyncJobSummary | null,
  ): SyncJobResponse | undefined {
    if (!job) return undefined;
    return {
      job_id: job.job_id,
      module_type_id: job.module_type_id,
      data_entry_type_id: job.data_entry_type_id,
      year: job.year,
      ingestion_method: job.ingestion_method as IngestionMethod,
      target_type: job.target_type as TargetType,
      state: job.state as IngestionState,
      result: job.result as IngestionResult,
      status_message: job.status_message,
      meta: job.meta,
    };
  }

  function getImportRow(sub: SubmoduleConfig): ImportRow {
    const mod =
      yearConfigStore.config?.config?.modules?.[String(sub.moduleTypeId)];
    const subConfig = mod?.submodules?.[String(sub.dataEntryTypeId)];
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
      lastDataJob: toSyncJobResponse(subConfig?.latest_data_job),
      lastApiDataJob: toSyncJobResponse(subConfig?.latest_api_data_job),
      lastFactorJob: toSyncJobResponse(subConfig?.latest_factor_job),
      lastReferenceJob: toSyncJobResponse(subConfig?.latest_reference_job),
    };
  }

  function submoduleShowsImportRow(sub: SubmoduleConfig): boolean {
    const row = getImportRow(sub);
    return row.hasData || row.hasFactors || row.hasOtherUpload;
  }

  function downloadLastCsv(row: ImportRow, targetType: TargetType) {
    const job =
      targetType === TargetType.DATA_ENTRIES
        ? row.lastDataJob
        : row.lastFactorJob;
    if (!job?.meta) return;
    const jobMeta = job.meta as Record<string, unknown>;
    const filePath = jobMeta?.processed_file_path as string;
    if (!filePath) return;
    const a = document.createElement('a');
    // ``?d=true`` — see useUploadCard.downloadLastCsv for why (Safari
    // strips the extension without backend Content-Disposition).
    a.href = `/api/v1/files/${filePath}?d=true`;
    a.download = filePath.split('/').pop() || filePath;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  function getUnifiedModuleConfigFromSub(sub: SubmoduleConfig) {
    const moduleName = getModuleNameFromSubmodule(sub);
    return moduleName ? getModule(moduleName) : null;
  }

  async function updateSubmoduleEnabled(
    sub: SubmoduleConfig,
    value: boolean,
  ): Promise<void> {
    const moduleKey = String(sub.moduleTypeId);
    const subKey =
      sub.dataEntryTypeId !== undefined
        ? String(sub.dataEntryTypeId)
        : undefined;
    if (!subKey) return;
    try {
      await yearConfigStore.updateConfig(yearConfigStore.selectedYear, {
        config: {
          modules: {
            [moduleKey]: { submodules: { [subKey]: { enabled: value } } },
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

  async function updateSubmoduleInputsDeactivated(
    sub: SubmoduleConfig,
    value: boolean,
  ): Promise<void> {
    const moduleKey = String(sub.moduleTypeId);
    const subKey =
      sub.dataEntryTypeId !== undefined
        ? String(sub.dataEntryTypeId)
        : undefined;
    if (!subKey) return;
    try {
      await yearConfigStore.updateConfig(yearConfigStore.selectedYear, {
        config: {
          modules: {
            [moduleKey]: {
              submodules: { [subKey]: { inputs_deactivated: value } },
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

  async function updateSubmoduleCsvDeactivated(
    sub: SubmoduleConfig,
    value: boolean,
  ): Promise<void> {
    const moduleKey = String(sub.moduleTypeId);
    const subKey =
      sub.dataEntryTypeId !== undefined
        ? String(sub.dataEntryTypeId)
        : undefined;
    if (!subKey) return;
    try {
      await yearConfigStore.updateConfig(yearConfigStore.selectedYear, {
        config: {
          modules: {
            [moduleKey]: {
              submodules: { [subKey]: { csv_deactivated: value } },
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

  function getSubmoduleThreshold(sub: SubmoduleConfig): number | null {
    const unifiedModule = getUnifiedModuleConfigFromSub(sub);
    return unifiedModule?.submodules[sub.key]?.threshold ?? null;
  }

  async function updateSubmoduleThreshold(
    sub: SubmoduleConfig,
    value: number | null,
  ): Promise<void> {
    const moduleKey = String(sub.moduleTypeId);
    const subKey =
      sub.dataEntryTypeId !== undefined
        ? String(sub.dataEntryTypeId)
        : undefined;
    if (!subKey) return;
    try {
      await yearConfigStore.updateConfig(yearConfigStore.selectedYear, {
        config: {
          modules: {
            [moduleKey]: {
              submodules: {
                [subKey]: { threshold: value },
              },
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

  const computedFactorRunning = ref<Record<string, boolean>>({});
  const anyComputedFactorRunning = computed(() =>
    Object.values(computedFactorRunning.value).some(Boolean),
  );

  async function confirmComputedFactorSync(
    sub: SubmoduleConfig,
    onCompleted: () => Promise<void>,
  ): Promise<void> {
    if (sub.dataEntryTypeId === undefined) return;
    computedFactorRunning.value[sub.key] = true;
    try {
      const jobId = await backofficeDataManagement.initiateComputedFactorSync(
        sub.moduleTypeId,
        sub.dataEntryTypeId,
        yearConfigStore.selectedYear,
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
          void onCompleted();
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
          void onCompleted();
        },
        () => {
          computedFactorRunning.value[sub.key] = false;
        },
        () => {
          void onCompleted();
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

  return {
    isSubmoduleEnabled,
    isSubmoduleIncomplete,
    isSubmoduleInputsDeactivated,
    isSubmoduleCsvDeactivated,
    getImportRow,
    submoduleShowsImportRow,
    downloadLastCsv,
    updateSubmoduleEnabled,
    updateSubmoduleInputsDeactivated,
    updateSubmoduleCsvDeactivated,
    getSubmoduleThreshold,
    updateSubmoduleThreshold,
    computedFactorRunning,
    anyComputedFactorRunning,
    confirmComputedFactorSync,
  };
}
