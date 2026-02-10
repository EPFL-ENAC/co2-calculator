<script setup lang="ts">
import { ref } from 'vue';
import { MODULES_LIST } from 'src/constant/modules';
import FilesUploadDialog from './FilesUploadDialog.vue';
import { useFilesStore } from 'src/stores/files';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';

const filesStore = useFilesStore();
const dataManagementStore = useBackofficeDataManagement();
interface Props {
  year: number;
}
defineProps<Props>();
const showUploadDialog = ref<boolean>(false);

const onFilesUploaded = () => {
  showUploadDialog.value = false;
};

const dataEntrySync = async (moduleTypeId: number, year: number) => {
  await dataManagementStore.initiateSync(
    moduleTypeId,
    year,
    'api',
    'data_entries',
  );
  // fetch status? // have sse ? how do we poll ?
};
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
          <q-btn
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
          />
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
                <q-btn
                  no-caps
                  color="accent"
                  icon="file_upload"
                  size="sm"
                  :label="$t('data_management_upload_csv_files')"
                  class="text-weight-medium"
                  @click="showUploadDialog = true"
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
