<script setup lang="ts">
import { ref, onUnmounted } from 'vue';
import { MODULES_LIST } from 'src/constant/modules';
import { enumSubmodule } from 'src/constant/modules';
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

/**
 * Initiate CSV upload sync for a module (MODULE_PER_YEAR bulk import).
 * For headcount: CSV contains unit_id (provider_code) column.
 * Backend resolves unit -> carbon_report_module_id per row.
 */
const onFilesUploaded = async (filePaths: string[]) => {
  showUploadDialog.value = false;

  if (!filePaths || filePaths.length === 0) {
    $q.notify({
      color: 'negative',
      message: $t('csv_no_files_uploaded'),
      position: 'top',
    });
  }

  // retrieve moduleTypeId from clicked module's upload button (stored in filesStore) and initiate sync for that module
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
      target_type: 'data_entries',
      file_path: filePath,
    };

    // Add data_entry_type_id for headcount (members only)
    // probably should be done in backend, but doing here for now to avoid changing existing backend endpoint signature
    if (module_type_id === 1) {
      syncParams.data_entry_type_id = enumSubmodule.member; // value: 1
    }

    const jobId = await dataManagementStore.initiateSync(syncParams);

    // Subscribe to job-specific SSE stream
    dataManagementStore.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        $q.notify({
          color: 'positive',
          message: $t('csv_sync_completed'),
          position: 'top',
        });
        console.log('Sync completed:', payload);
      },
      (payload?: JobUpdatePayload) => {
        $q.notify({
          color: 'negative',
          message: `${$t('csv_sync_failed')} ${payload?.status_message || ''}`,
          position: 'top',
        });
        console.error('Sync failed:', payload);
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

const openUploadCsvDialog = (moduleTypeId: number, year: number) => {
  // store moduleTypeId in filesStore to retrieve later when files are uploaded
  // TODO: FORBID USER to CHANGE
  filesStore.currentUploadModuleTypeId = moduleTypeId;
  filesStore.currentUploadYear = year;
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
          <!-- <q-btn
            no-caps
            color="accent"
            icon="file_upload"
            size="sm"
            :label="$t('data_management_upload_csv_files')"
            class="text-weight-medium on-right"
            @click="showUploadDialog = true"
          />
          <q-btn
            no-caps
            color="accent"
            icon="file_copy"
            size="sm"
            :label="$t('data_management_copy_previous_year')"
            class="text-weight-medium on-right"
          /> -->
        </template>
        <div>
          {{
            $t('data_management_data_imports_count', {
              count: MODULES_LIST.length,
            })
          }}
        </div>
      </q-banner>
      <q-markup-table flat bordered>
        <thead>
          <tr>
            <th align="left">{{ $t('data_management_category') }}</th>
            <th align="left">
              {{ $t('data_management_description') }}
            </th>
            <th align="left">{{ $t('data_management_data') }}</th>
            <th align="left">{{ $t('data_management_factor') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="module in MODULES_LIST" :key="module">
            <td class="text-weight-medium" align="left">{{ $t(module) }}</td>
            <td align="left"></td>
            <td align="left">
              <div class="q-mb-sm">
                <q-icon name="warning" size="xs" color="warning" />
                <span class="q-ml-sm text-negative">{{
                  $t('data_management_no_data')
                }}</span>
              </div>
              <div>
                <!-- DATA buttons -->
                <q-btn
                  no-caps
                  color="accent"
                  icon="file_upload"
                  size="sm"
                  :label="$t('data_management_upload_csv_files')"
                  class="text-weight-medium"
                  @click="
                    openUploadCsvDialog(MODULES_LIST.indexOf(module) + 1, year)
                  "
                />
                <!-- TODO: use enum for data_module_type_id -->
                <q-btn
                  no-caps
                  color="accent"
                  icon="link"
                  size="sm"
                  :label="$t('data_management_connect_api')"
                  class="text-weight-medium on-right"
                  @click="dataEntrySync(MODULES_LIST.indexOf(module) + 1, year)"
                />
                <q-btn
                  no-caps
                  color="accent"
                  icon="file_copy"
                  size="sm"
                  :label="$t('data_management_copy_previous_year')"
                  class="text-weight-medium on-right"
                />
              </div>
            </td>
            <td align="left">
              <div class="q-mb-sm">
                <q-icon name="warning" size="xs" color="warning" />
                <span class="q-ml-sm text-negative">{{
                  $t('data_management_no_data')
                }}</span>
              </div>
              <div>
                <!-- FACTORS buttons -->
                <q-btn
                  no-caps
                  color="accent"
                  icon="file_upload"
                  size="sm"
                  :label="$t('data_management_upload_csv_files')"
                  class="text-weight-medium"
                />
                <q-btn
                  no-caps
                  color="accent"
                  icon="link"
                  size="sm"
                  :label="$t('data_management_connect_api')"
                  class="text-weight-medium on-right"
                />
                <q-btn
                  no-caps
                  color="accent"
                  icon="file_copy"
                  size="sm"
                  :label="$t('data_management_copy_previous_year')"
                  class="text-weight-medium on-right"
                />
              </div>
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
