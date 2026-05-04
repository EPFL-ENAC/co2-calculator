<script setup lang="ts">
import { useFilesStore } from 'src/stores/files';
import { useI18n } from 'vue-i18n';

const filesStore = useFilesStore();
const { t: $t } = useI18n();
</script>

<template>
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
</template>
