import { computed } from 'vue';
import {
  useYearConfigStore,
  type SyncJobSummary,
  type ModuleConfig as ModuleConfigType,
} from 'src/stores/yearConfig';
import {
  IngestionState,
  IngestionResult,
  IngestionMethod,
  TargetType,
  type ImportRow,
  type SyncJobResponse,
} from 'src/stores/backofficeDataManagement';
import {
  MODULE_SUBMODULES,
  MODULE_COMMON_UPLOADS,
  type SubmoduleConfig as SubmoduleConfigItem,
} from 'src/constant/backoffice-module-config';
import type { Module } from 'src/constant/modules';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';

interface UseModuleConfigOptions {
  module: string;
  selectedYear: number;
}

export function useModuleConfig(options: UseModuleConfigOptions) {
  const { t: $t } = useI18n();
  const yearConfigStore = useYearConfigStore();

  const { isModuleEnabled, isModuleIncomplete, getModule } = yearConfigStore;

  type UncertaintyTag = ModuleConfigType['uncertainty_tag'];

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

  function getImportRow(sub: SubmoduleConfigItem): ImportRow {
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
    };
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

  function getModuleTypeIdFromName(module: string): number {
    const subs =
      MODULE_SUBMODULES[module as keyof typeof MODULE_SUBMODULES] ?? [];
    return subs.length > 0 ? subs[0].moduleTypeId : 0;
  }

  function getUnifiedModuleConfig(module: string) {
    return getModule(module as Module);
  }

  async function updateModuleEnabled(
    module: string,
    value: boolean,
  ): Promise<void> {
    const moduleTypeId = getModuleTypeIdFromName(module);
    if (!moduleTypeId) return;
    try {
      await yearConfigStore.updateConfig(options.selectedYear, {
        config: { modules: { [String(moduleTypeId)]: { enabled: value } } },
      });
      Notify.create({ type: 'positive', message: $t('year_config_saved') });
    } catch {
      Notify.create({
        type: 'negative',
        message: $t('year_config_save_error'),
      });
    }
  }

  function getModuleUncertainty(module: string): UncertaintyTag {
    const unifiedConfig = getUnifiedModuleConfig(module);
    return unifiedConfig?.uncertainty_tag ?? 'medium';
  }

  async function updateModuleUncertainty(
    module: string,
    value: UncertaintyTag,
  ): Promise<void> {
    const moduleTypeId = getModuleTypeIdFromName(module);
    if (!moduleTypeId) return;
    try {
      await yearConfigStore.updateConfig(options.selectedYear, {
        config: {
          modules: { [String(moduleTypeId)]: { uncertainty_tag: value } },
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

  const commonUploads = computed(
    () =>
      MODULE_COMMON_UPLOADS[
        options.module as keyof typeof MODULE_COMMON_UPLOADS
      ] || [],
  );
  const submodules = computed(
    () =>
      MODULE_SUBMODULES[options.module as keyof typeof MODULE_SUBMODULES] || [],
  );

  return {
    isModuleEnabled,
    isModuleIncomplete,
    getModuleTypeIdFromName,
    getModuleUncertainty,
    updateModuleEnabled,
    updateModuleUncertainty,
    getImportRow,
    downloadLastCsv,
    commonUploads,
    submodules,
  };
}
