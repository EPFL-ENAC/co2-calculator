<script setup lang="ts">
import { ref, onUnmounted } from 'vue';
import FilesUploadDialog from './FilesUploadDialog.vue';
import { useFilesStore } from 'src/stores/files';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';
import type {
  JobUpdatePayload,
  InitiateSyncParams,
} from 'src/stores/backofficeDataManagement';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

const filesStore = useFilesStore();
const dataManagementStore = useBackofficeDataManagement();
const $q = useQuasar();
const { t: $t } = useI18n();

interface Props {
  year: number;
}
defineProps<Props>();
const showUploadDialog = ref<boolean>(false);
const uploadTargetType = ref<'data_entries' | 'factors'>('data_entries');
const uploadFactorVariant = ref<string | null>(null);
const uploadDataEntryTypeId = ref<number | null>(null);

interface ImportRow {
  key: string;
  labelKey: string;
  moduleTypeId: number;
  dataEntryTypeId?: number;
  factorVariant?: 'plane' | 'train';
  hasFactors: boolean;
  hasApi: boolean;
  hasData: boolean; //
  other?: string;
  hasOtherUpload?: boolean;
  isDisabled?: boolean;
}

const importRows: ImportRow[] = [
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

/**
 * Initiate CSV upload sync for a module (MODULE_PER_YEAR bulk import).
 * For headcount: CSV contains unit_id (institutional_id) column.
 * Backend resolves unit -> carbon_report_module_id per row.
 */
const onFilesUploaded = async (filePaths: string[]) => {
  showUploadDialog.value = false;

  if (!filePaths || filePaths.length === 0) {
    $q.notify({
      color: 'negative',
      message: $t('csv_no_files_uploaded'),
      position: 'top',
      closeBtn: true,
    });
    return;
  }

  // retrieve moduleTypeId from clicked module's upload button (stored in filesStore) and initiate sync for that module
  // Storing per-click UI context (moduleTypeId, year)
  // in a global store makes the flow fragile (e.g., multiple dialogs, rapid clicks, navigation)
  // and the TODO comment is unclear.
  // Prefer passing moduleTypeId/year through the dialog component (props/events) or storing them as local refs in this component;
  // also replace the TODO with an actionable comment (or enforce the restriction in code).
  const module_type_id = filesStore.currentUploadModuleTypeId;
  if (module_type_id === null) {
    $q.notify({
      color: 'negative',
      message: `${$t('csv_sync_failed_to_initiate')}: missing moduleTypeId`,
      position: 'top',
    });
    return;
  }
  const year = filesStore.currentUploadYear;
  if (year === null) {
    $q.notify({
      color: 'negative',
      message: `${$t('csv_sync_failed_to_initiate')}: missing year`,
      position: 'top',
    });
    return;
  }

  // start initiating sync for the files
  // subscribe to job updates and show notifications on completion/failure

  const filePath = filePaths[0]; // use the path of the first uploaded file (assuming single file upload for now)

  try {
    $q.notify({
      color: 'info',
      message: $t('csv_sync_starting'),
      position: 'top',
    });

    // For headcount (moduleTypeId=1): specify data_entry_type_id for members
    const syncParams: InitiateSyncParams = {
      module_type_id,
      year,
      provider_type: 'csv',
      target_type: uploadTargetType.value,
      file_path: filePath,
    };

    if (uploadDataEntryTypeId.value !== null) {
      syncParams.data_entry_type_id = uploadDataEntryTypeId.value;
    } else if (
      uploadTargetType.value === 'data_entries' &&
      module_type_id === 1
    ) {
      // Keep existing headcount default behavior
      syncParams.data_entry_type_id = 1;
    }

    if (uploadTargetType.value === 'factors' && uploadFactorVariant.value) {
      syncParams.config = {
        ...(syncParams.config || {}),
        factor_variant: uploadFactorVariant.value,
      };
    }

    const jobId = await dataManagementStore.initiateSync(syncParams);

    // Subscribe to job-specific SSE stream
    dataManagementStore.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        // Determine notification type based on result (SUCCESS, WARNING, ERROR)
        const result = payload?.result;
        const rowsProcessed = payload?.meta?.rows_processed as
          | number
          | undefined;
        const rowsSkipped = payload?.meta?.rows_skipped as number | undefined;

        let color: string;
        let message: string;
        let caption: string;

        if (result === 1) {
          // WARNING: some rows skipped
          color = 'warning';
          message = $t('csv_sync_completed_with_warnings');
          caption = $t('csv_sync_warnings_caption', {
            processed: rowsProcessed || 0,
            skipped: rowsSkipped || 0,
          });
        } else if (result === 0) {
          // SUCCESS: all rows processed
          color = 'positive';
          message = $t('csv_sync_completed');
          caption = $t('csv_sync_success_caption', {
            processed: rowsProcessed || 0,
          });
        } else {
          // ERROR: nothing processed or failed
          color = 'negative';
          message = $t('csv_sync_failed');
          caption = payload?.status_message || '';
        }

        $q.notify({
          color,
          message,
          caption,
          position: 'top',
          timeout: 5000,
        });
        console.log('Sync completed:', payload);
      },
      (payload?: JobUpdatePayload) => {
        $q.notify({
          color: 'negative',
          message: $t('csv_sync_failed'),
          caption: payload?.status_message || $t('csv_sync_failed_caption'),
          position: 'top',
          timeout: 5000,
        });
        console.error('Sync failed:', payload);
      },
      () => {
        $q.notify({
          color: 'negative',
          message: $t('csv_sync_connection_lost'),
          caption: $t('csv_sync_connection_lost_caption'),
          position: 'top',
          timeout: 30000,
        });
      },
    );

    $q.notify({
      color: 'positive',
      message: $t('csv_sync_initiated'),
      position: 'top',
    });
  } catch (err) {
    console.error('Failed to initiate sync:', err);
    $q.notify({
      color: 'negative',
      message:
        err instanceof Error ? err.message : $t('csv_sync_failed_to_initiate'),
      position: 'top',
    });
  }
};

const dataEntrySync = async (moduleTypeId: number, year: number) => {
  await dataManagementStore.initiateSync({
    module_type_id: moduleTypeId,
    year,
    provider_type: 'api',
    target_type: 'data_entries',
  });
};

const openUploadCsvDialog = (row: ImportRow, year: number) => {
  // store moduleTypeId in filesStore to retrieve later when files are uploaded
  // TODO: FORBID USER to CHANGE
  filesStore.currentUploadModuleTypeId = row.moduleTypeId;
  filesStore.currentUploadYear = year;
  uploadTargetType.value = 'data_entries';
  uploadFactorVariant.value = null;
  uploadDataEntryTypeId.value = row.dataEntryTypeId ?? null;
  showUploadDialog.value = true;
};

const openUploadFactorsDialog = (row: ImportRow, year: number) => {
  filesStore.currentUploadModuleTypeId = row.moduleTypeId;
  filesStore.currentUploadYear = year;
  uploadTargetType.value = 'factors';
  uploadDataEntryTypeId.value = row.dataEntryTypeId ?? null;
  uploadFactorVariant.value = row.factorVariant ?? null;
  showUploadDialog.value = true;
};

// Unsubscribe from SSE when component unmounts
onUnmounted(() => {
  dataManagementStore.unsubscribeFromJobUpdates();
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
                <div class="q-mb-sm">
                  <q-icon name="warning" size="xs" color="warning" />
                  <span class="q-ml-sm text-warning">{{
                    $t('data_management_no_data_warning')
                  }}</span>
                </div>
                <div>
                  <q-btn
                    no-caps
                    color="accent"
                    icon="file_upload"
                    size="sm"
                    :label="$t('data_management_upload_csv_files')"
                    class="text-weight-medium"
                    :disable="row.isDisabled"
                    @click="openUploadCsvDialog(row, year)"
                  />
                  <q-btn
                    v-if="row.hasApi"
                    no-caps
                    color="accent"
                    icon="link"
                    size="sm"
                    :label="$t('data_management_connect_api')"
                    class="text-weight-medium on-right"
                    :disable="row.isDisabled"
                    @click="dataEntrySync(row.moduleTypeId, year)"
                  />
                  <q-btn
                    no-caps
                    color="accent"
                    icon="file_copy"
                    size="sm"
                    :label="$t('data_management_copy_previous_year')"
                    class="text-weight-medium on-right"
                    :disable="row.isDisabled"
                  />
                </div>
              </template>
              <span v-else class="text-grey-5">—</span>
            </td>
            <td align="left">
              <template v-if="row.hasFactors">
                <div class="q-mb-sm">
                  <q-icon name="error" size="xs" color="negative" />
                  <span class="q-ml-sm text-negative">{{
                    $t('data_management_no_factors_error')
                  }}</span>
                </div>
                <div>
                  <q-btn
                    no-caps
                    color="accent"
                    icon="file_upload"
                    size="sm"
                    :label="$t('data_management_upload_csv_files')"
                    class="text-weight-medium"
                    :disable="row.isDisabled"
                    @click="openUploadFactorsDialog(row, year)"
                  />
                  <q-btn
                    no-caps
                    color="accent"
                    icon="file_copy"
                    size="sm"
                    :label="$t('data_management_copy_previous_year')"
                    class="text-weight-medium on-right"
                    :disable="row.isDisabled"
                  />
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
    <files-upload-dialog
      v-model="showUploadDialog"
      @files-uploaded="onFilesUploaded"
    />
  </q-card>
</template>
