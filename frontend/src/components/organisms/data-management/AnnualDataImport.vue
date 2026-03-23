<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useFilesStore } from 'src/stores/files';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';
import type {
  SyncJobResponse,
  DataIngestionJob,
} from 'src/stores/backofficeDataManagement';
import { useI18n } from 'vue-i18n';
import DataEntryDialog from './DataEntryDialog.vue';

const filesStore = useFilesStore();
const dataManagementStore = useBackofficeDataManagement();
const { t: $t } = useI18n();

interface Props {
  year: number;
}
const props = defineProps<Props>();

interface ImportRow {
  key: string;
  labelKey: string;
  moduleTypeId: number;
  dataEntryTypeId?: number;
  factorVariant?: 'plane' | 'train';
  hasFactors: boolean;
  hasApi: boolean;
  hasData: boolean;
  other?: string;
  hasOtherUpload?: boolean;
  isDisabled?: boolean;
  // Job tracking fields
  lastDataJob?: SyncJobResponse;
  lastFactorJob?: SyncJobResponse;
}

// Static row definitions (base configuration)
const BASE_IMPORT_ROWS: Omit<ImportRow, 'lastDataJob' | 'lastFactorJob'>[] = [
  {
    key: 'headcount_members',
    labelKey: 'data_management_row_headcount_members',
    moduleTypeId: 1,
    dataEntryTypeId: 1,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'headcount_students',
    labelKey: 'data_management_row_headcount_students',
    moduleTypeId: 1,
    dataEntryTypeId: 2,
    hasFactors: true,
    hasApi: false,
    hasData: false,
  },
  {
    key: 'travel_train',
    labelKey: 'data_management_row_travel_train',
    moduleTypeId: 2,
    dataEntryTypeId: 21,
    factorVariant: 'train',
    hasFactors: true,
    hasApi: false,
    other: 'data_management_other_train_stations',
    hasOtherUpload: true,
    hasData: true,
  },
  {
    key: 'travel_plane',
    labelKey: 'data_management_row_travel_plane',
    moduleTypeId: 2,
    dataEntryTypeId: 20,
    factorVariant: 'plane',
    hasFactors: true,
    hasApi: true,
    other: 'data_management_other_airports',
    hasOtherUpload: true,
    hasData: true,
  },
  {
    key: 'buildings_rooms',
    labelKey: 'data_management_row_buildings_rooms',
    moduleTypeId: 3,
    dataEntryTypeId: 30,
    hasFactors: true,
    hasApi: false,
    other: 'data_management_other_institution_rooms',
    hasOtherUpload: true,
    hasData: true,
  },
  {
    key: 'buildings_energy_combustion',
    labelKey: 'data_management_row_buildings_energy_combustion',
    moduleTypeId: 3,
    dataEntryTypeId: 31,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'process_emissions',
    labelKey: 'data_management_row_process_emissions',
    moduleTypeId: 8,
    dataEntryTypeId: 50,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'equipment',
    labelKey: 'data_management_row_equipment',
    moduleTypeId: 4,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'purchases_common',
    labelKey: 'data_management_row_purchases_common',
    moduleTypeId: 5,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'purchases_additional',
    labelKey: 'data_management_row_purchases_additional',
    moduleTypeId: 5,
    dataEntryTypeId: 67,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'research_facilities',
    labelKey: 'data_management_row_research_facilities',
    moduleTypeId: 6,
    dataEntryTypeId: 70,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'research_facilities_animal',
    labelKey: 'data_management_row_research_facilities_animal',
    moduleTypeId: 6,
    dataEntryTypeId: 71,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'external_clouds',
    labelKey: 'data_management_row_external_clouds',
    moduleTypeId: 7,
    dataEntryTypeId: 40,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'external_ai',
    labelKey: 'data_management_row_external_ai',
    moduleTypeId: 7,
    dataEntryTypeId: 41,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'food',
    labelKey: 'data_management_row_food',
    moduleTypeId: 10,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'waste',
    labelKey: 'data_management_row_waste',
    moduleTypeId: 11,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'commuting',
    labelKey: 'data_management_row_commuting',
    moduleTypeId: 9,
    hasFactors: true,
    hasApi: false,
    hasData: true,
  },
  {
    key: 'grey_energy',
    labelKey: 'data_management_row_grey_energy',
    moduleTypeId: 12,
    hasFactors: false,
    hasApi: false,
    isDisabled: true,
    hasData: true,
  },
];

// Reactive map of jobs by module_type_id and target_type
const jobsByModule = ref<Map<string, DataIngestionJob>>(new Map());

// Dialog state
const showDataEntryDialog = ref<boolean>(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<'data_entries' | 'factors'>('data_entries');

// Fetch sync jobs and store in reactive map
async function loadSyncJobs() {
  try {
    // Use the new endpoint that returns pre-filtered latest jobs
    const jobs = await dataManagementStore.fetchLatestSyncJobsByYear(
      props.year,
    );

    // Build new map and replace (triggers reactivity)
    // Key by module_type_id-target_type for general matching
    const newMap = new Map<string, DataIngestionJob>();
    jobs.forEach((job: DataIngestionJob) => {
      // Use root module_type_id for general matching
      const key = `${job.module_type_id}-${job.target_type}`;
      newMap.set(key, job);
    });
    jobsByModule.value = newMap;
  } catch (err) {
    console.error('Failed to load sync jobs:', err);
  }
}

// Computed import rows with latest job data
const importRows = computed<ImportRow[]>(() => {
  return BASE_IMPORT_ROWS.map((row) => {
    // Get all jobs for this module_type_id and target_type
    const allDataJobs = Array.from(jobsByModule.value.values()).filter(
      (j) => j.module_type_id === row.moduleTypeId && j.target_type === 0,
    );
    const allFactorJobs = Array.from(jobsByModule.value.values()).filter(
      (j) => j.module_type_id === row.moduleTypeId && j.target_type === 1,
    );

    // If row has dataEntryTypeId, filter by it from meta.config.data_entry_type_id
    let dataJob: DataIngestionJob | undefined;
    let factorJob: DataIngestionJob | undefined;

    if (row.dataEntryTypeId !== undefined) {
      // Match by data_entry_type_id in meta.config
      dataJob = allDataJobs.find((j) => {
        const configDataEntryTypeId = (j.meta?.config as any)
          ?.data_entry_type_id;
        return configDataEntryTypeId === row.dataEntryTypeId;
      });

      factorJob = allFactorJobs.find((j) => {
        const configDataEntryTypeId = (j.meta?.config as any)
          ?.data_entry_type_id;
        return configDataEntryTypeId === row.dataEntryTypeId;
      });
    } else {
      // No specific data_entry_type_id, use first available
      dataJob = allDataJobs[0];
      factorJob = allFactorJobs[0];
    }

    return {
      ...row,
      lastDataJob: dataJob
        ? ({
            job_id: dataJob.job_id,
            module_type_id: dataJob.module_type_id,
            year: dataJob.year,
            target_type: dataJob.target_type as 0 | 1,
            state: dataJob.state,
            result: dataJob.result,
            status_message: dataJob.status_message,
            meta: dataJob.meta,
          } as SyncJobResponse)
        : undefined,
      lastFactorJob: factorJob
        ? ({
            job_id: factorJob.job_id,
            module_type_id: factorJob.module_type_id,
            year: factorJob.year,
            target_type: factorJob.target_type as 0 | 1,
            state: factorJob.state,
            result: factorJob.result,
            status_message: factorJob.status_message,
            meta: factorJob.meta,
          } as SyncJobResponse)
        : undefined,
    };
  });
});

// Button color computation
const getDataButtonColor = computed(() => {
  return (row: ImportRow): string => {
    if (row.isDisabled) return 'grey-4';
    if (!row.lastDataJob) return 'accent'; // No job yet
    if (row.lastDataJob.result === 2) return 'negative'; // ERROR
    if (row.lastDataJob.result === 1) return 'warning'; // WARNING
    return 'positive'; // SUCCESS or default
  };
});

const getFactorButtonColor = computed(() => {
  return (row: ImportRow): string => {
    if (row.isDisabled) return 'grey-4';
    if (!row.lastFactorJob) return 'accent'; // No job yet
    if (row.lastFactorJob.result === 2) return 'negative'; // ERROR
    if (row.lastFactorJob.result === 1) return 'warning'; // WARNING
    return 'positive'; // SUCCESS or default
  };
});

// Button label computation
const getDataButtonLabel = computed(() => {
  return (row: ImportRow): string => {
    if (row.isDisabled) return '';
    return row.lastDataJob
      ? $t('data_management_reupload_data')
      : $t('data_management_add_data');
  };
});

const getFactorButtonLabel = computed(() => {
  return (row: ImportRow): string => {
    if (row.isDisabled) return '';
    return row.lastFactorJob
      ? $t('data_management_reupload_factors')
      : $t('data_management_add_factors');
  };
});

// Get last import info
const getLastDataImportInfo = computed(() => {
  return (
    row: ImportRow,
  ): { date: string; rows: number; fileName: string } | null => {
    const job = row.lastDataJob;
    if (!job || !job.meta) return null;

    const meta = job.meta as Record<string, unknown>;
    const rowsProcessed = (meta.rows_processed as number) || 0;
    const filePath = (meta.file_path as string) || '';
    const fileName = filePath.split('/').pop() || '';

    return {
      date: $t('data_management_last_import_date'),
      rows: rowsProcessed,
      fileName,
    };
  };
});

const getLastFactorImportInfo = computed(() => {
  return (
    row: ImportRow,
  ): { date: string; rows: number; fileName: string } | null => {
    const job = row.lastFactorJob;
    if (!job || !job.meta) return null;

    const meta = job.meta as Record<string, unknown>;
    const rowsProcessed = (meta.rows_processed as number) || 0;
    const filePath = (meta.file_path as string) || '';
    const fileName = filePath.split('/').pop() || '';

    return {
      date: $t('data_management_last_import_date'),
      rows: rowsProcessed,
      fileName,
    };
  };
});

// Open dialog
const openDataEntryDialog = (
  row: ImportRow,
  targetType: 'data_entries' | 'factors',
) => {
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
};

// Handle job completion - reload jobs to update button states
const handleJobCompleted = async () => {
  await loadSyncJobs();
};

// Download last CSV
const downloadLastCsv = (
  row: ImportRow,
  targetType: 'data_entries' | 'factors',
) => {
  const job =
    targetType === 'data_entries' ? row.lastDataJob : row.lastFactorJob;
  if (!job || !job.meta) return;

  const meta = job.meta as Record<string, unknown>;
  const filePath = (meta.file_path as string) || '';
  if (!filePath) return;

  const fileName = filePath.split('/').pop() || filePath;
  const a = document.createElement('a');
  a.href = `/files/${filePath}`;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
};

// Unsubscribe from SSE when component unmounts
onUnmounted(() => {
  dataManagementStore.unsubscribeFromJobUpdates();
});

// Load jobs on mount
onMounted(() => {
  loadSyncJobs();
});
</script>

<template>
  <q-card flat bordered class="q-pa-md q-mb-xl">
    <div class="text-h5 text-weight-medium">
      <q-icon name="file_download" color="accent" size="sm" class="on-left" />
      <span>{{ $t('data_management_annual_data_import') }}</span>
    </div>
    <div class="q-my-md">
      {{ $t('data_management_annual_data_import_hint') }}
    </div>
    <div>
      <q-banner class="bg-grey-2 text-grey-8">
        <q-icon name="info" size="xs" class="on-left" />
        <span class="q-ml-sm">
          {{
            filesStore.tempFiles.length > 0
              ? $t('data_management_temp_files_uploaded', {
                  count: filesStore.tempFiles.length,
                })
              : $t('data_management_no_temp_files_uploaded')
          }}
        </span>
        <q-btn
          v-if="filesStore.tempFiles.length > 0"
          no-caps
          outline
          color="negative"
          icon="delete"
          size="sm"
          :label="$t('data_management_delete_temp_files')"
          class="text-weight-medium on-right"
          @click="filesStore.deleteTempFiles()"
        />
      </q-banner>
    </div>
    <div>
      <q-banner inline-actions class="q-px-none">
        <template #action>
          <q-btn
            no-caps
            outline
            color="secondary"
            icon="file_download"
            size="sm"
            :label="$t('data_management_download_csv_templates')"
            class="text-weight-medium"
          />
        </template>
        <div>
          {{
            $t('data_management_data_imports_count', {
              count: importRows.length,
            })
          }}
        </div>
      </q-banner>
      <q-markup-table flat bordered>
        <thead>
          <tr>
            <th align="left">{{ $t('data_management_category') }}</th>
            <th align="left">{{ $t('data_management_data') }}</th>
            <th align="left">{{ $t('data_management_factor') }}</th>
            <th align="left">{{ $t('data_management_column_other') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in importRows" :key="row.key">
            <td class="text-weight-medium" align="left">
              {{ $t(row.labelKey) }}
              <q-badge
                v-if="row.isDisabled"
                color="grey-4"
                text-color="grey-8"
                :label="$t('data_management_tbd')"
                class="q-ml-sm"
              />
            </td>
            <td align="left">
              <template v-if="row.hasData">
                <q-btn
                  :color="getDataButtonColor(row)"
                  icon="add"
                  size="sm"
                  :label="getDataButtonLabel(row)"
                  class="text-weight-medium"
                  :disable="row.isDisabled"
                  @click="openDataEntryDialog(row, 'data_entries')"
                />
                <div
                  v-if="row.lastDataJob && getLastDataImportInfo(row)"
                  class="q-mt-xs text-caption text-grey-7"
                >
                  <div>
                    {{ getLastDataImportInfo(row)!.rows }}
                    {{ $t('data_management_rows_imported') }}
                  </div>
                  <div class="row items-center q-gutter-xs">
                    <span>{{ getLastDataImportInfo(row)!.fileName }}</span>
                    <q-btn
                      flat
                      dense
                      round
                      icon="download"
                      size="xs"
                      color="grey-6"
                      @click="downloadLastCsv(row, 'data_entries')"
                    >
                      <q-tooltip>{{
                        $t('data_management_download_last_csv')
                      }}</q-tooltip>
                    </q-btn>
                  </div>
                </div>
              </template>
              <span v-else class="text-grey-5">—</span>
            </td>
            <td align="left">
              <template v-if="row.hasFactors">
                <q-btn
                  :color="getFactorButtonColor(row)"
                  icon="add"
                  size="sm"
                  :label="getFactorButtonLabel(row)"
                  class="text-weight-medium"
                  :disable="row.isDisabled"
                  @click="openDataEntryDialog(row, 'factors')"
                />
                <div
                  v-if="row.lastFactorJob && getLastFactorImportInfo(row)"
                  class="q-mt-xs text-caption text-grey-7"
                >
                  <div>
                    {{ getLastFactorImportInfo(row)!.rows }}
                    {{ $t('data_management_rows_imported') }}
                  </div>
                  <div class="row items-center q-gutter-xs">
                    <span>{{ getLastFactorImportInfo(row)!.fileName }}</span>
                    <q-btn
                      flat
                      dense
                      round
                      icon="download"
                      size="xs"
                      color="grey-6"
                      @click="downloadLastCsv(row, 'factors')"
                    >
                      <q-tooltip>{{
                        $t('data_management_download_last_csv')
                      }}</q-tooltip>
                    </q-btn>
                  </div>
                </div>
              </template>
              <span v-else class="text-grey-5">—</span>
            </td>
            <td align="left">
              <template v-if="row.other">
                <div class="q-mb-xs text-caption text-grey-7">
                  {{ $t(row.other) }}
                </div>
                <q-btn
                  v-if="row.hasOtherUpload"
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
              </template>
            </td>
          </tr>
        </tbody>
      </q-markup-table>
    </div>

    <data-entry-dialog
      v-model="showDataEntryDialog"
      :row="dialogCurrentRow || ({} as ImportRow)"
      :year="year"
      :target-type="dialogTargetType"
      @completed="handleJobCompleted"
    />
  </q-card>
</template>
