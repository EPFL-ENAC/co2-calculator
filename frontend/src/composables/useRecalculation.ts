import { ref } from 'vue';
import {
  useBackofficeDataManagement,
  IngestionResult,
  type JobUpdatePayload,
} from 'src/stores/backofficeDataManagement';
import {
  useYearConfigStore,
  type RecalculationStatusEntry,
} from 'src/stores/yearConfig';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import type { SubmoduleConfig as SubmoduleConfigItem } from 'src/constant/backoffice-module-config';

interface UseRecalculationOptions {
  selectedYear: number;
}

export function useRecalculation(options: UseRecalculationOptions) {
  const { t: $t } = useI18n();
  const backofficeDataManagement = useBackofficeDataManagement();
  const yearConfigStore = useYearConfigStore();

  const recalcRunning = ref<Record<number, boolean>>({});
  const recalcTypeRunning = ref<Record<string, boolean>>({});

  async function refreshAfterRecalc(): Promise<void> {
    await yearConfigStore.fetchConfig(options.selectedYear);
  }

  function getRecalcStatus(
    sub: SubmoduleConfigItem,
  ): RecalculationStatusEntry | undefined {
    if (sub.dataEntryTypeId === undefined) return undefined;
    return yearConfigStore.recalculationStatus[sub.moduleTypeId]?.data_entry_types.find(
      (d) => d.data_entry_type_id === sub.dataEntryTypeId,
    );
  }

  async function confirmModuleRecalculation(
    moduleTypeId: number,
  ): Promise<void> {
    recalcRunning.value[moduleTypeId] = true;
    try {
      const jobId =
        await backofficeDataManagement.initiateModuleEmissionRecalculation(
          moduleTypeId,
          options.selectedYear,
          true,
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
          void refreshAfterRecalc();
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
          void refreshAfterRecalc();
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
      const jobId =
        await backofficeDataManagement.initiateEmissionRecalculation(
          sub.moduleTypeId,
          sub.dataEntryTypeId,
          options.selectedYear,
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
          void refreshAfterRecalc();
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
          void refreshAfterRecalc();
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

  function staleTypesForModule(moduleTypeId: number): RecalculationStatusEntry[] {
    return (
      yearConfigStore.recalculationStatus[moduleTypeId]?.data_entry_types.filter(
        (d) => d.needs_recalculation,
      ) ?? []
    );
  }

  return {
    recalcRunning,
    recalcTypeRunning,
    getRecalcStatus,
    confirmModuleRecalculation,
    triggerTypeRecalculation,
    staleTypesForModule,
  };
}
