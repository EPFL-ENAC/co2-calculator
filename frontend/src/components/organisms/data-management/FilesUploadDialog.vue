<script lang="ts" setup>
import { ref, watch } from 'vue';
import { useFilesStore, type FileObject } from 'src/stores/files';

const filesStore = useFilesStore();

interface Props {
  modelValue: boolean;
}
const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'filesUploaded'): void;
}>();
const showDialog = ref<boolean>(false);
watch(
  () => props.modelValue,
  (newVal) => {
    showDialog.value = newVal;
    selectedFiles.value = [];
  },
);
watch(showDialog, (newVal) => {
  emit('update:modelValue', newVal);
});
const selectedFiles = ref<FileObject[]>([]);
const isUploading = ref<boolean>(false);

const uploadFiles = async () => {
  if (!selectedFiles.value) return;
  isUploading.value = true;
  try {
    await filesStore.uploadTempFiles(selectedFiles.value);
    emit('filesUploaded');
    showDialog.value = false;
  } catch (error) {
    console.error('Error uploading files:', error);
  } finally {
    isUploading.value = false;
  }
};
</script>

<template>
  <q-dialog v-model="showDialog" class="modal-grid">
    <q-card class="column modal modal--lg">
      <q-card-section class="flex justify-between items-center flex-shrink">
        <div class="text-h4 text-weight-medium">
          {{ $t('common_upload_csv') }}
        </div>
        <q-btn
          v-close-popup
          flat
          size="md"
          icon="o_close"
          color="grey-6"
          class="text-weight-medium"
        />
      </q-card-section>
      <q-separator />
      <q-card-section>
        <div class="text-h5 q-mb-md">
          {{ $t('data_management_upload_csv_files') }}
        </div>
        <q-file
          v-model="selectedFiles"
          dense
          outlined
          multiple
          :hint="$t('data_management_supported_file_types')"
          counter
          accept=".csv, text/csv"
          class="q-mb-md"
        />
        <q-btn
          :label="$t('data_management_upload')"
          size="sm"
          color="accent"
          :disabled="
            !selectedFiles || selectedFiles.length === 0 || isUploading
          "
          @click="uploadFiles"
        />
        <q-linear-progress
          v-if="isUploading"
          indeterminate
          color="accent"
          class="q-mt-md"
        />
      </q-card-section>
    </q-card>
  </q-dialog>
</template>
