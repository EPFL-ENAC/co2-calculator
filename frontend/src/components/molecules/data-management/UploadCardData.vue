<script setup lang="ts">
import { useUploadCard } from 'src/composables/useUploadCard';
import {
  TargetType,
  IngestionState,
} from 'src/stores/backofficeDataManagement';
import type {
  ImportRow,
  RecalculationStatus,
} from 'src/stores/backofficeDataManagement';
import UploadCard from './UploadCard.vue';

interface Props {
  row: ImportRow;
  isDisabled?: boolean;
  recalcRunning?: boolean;
  recalcStatus?: RecalculationStatus;
}

const props = withDefaults(defineProps<Props>(), {
  isDisabled: false,
  recalcRunning: false,
  recalcStatus: undefined,
});

const emit = defineEmits<{
  (e: 'upload', row: ImportRow, targetType: TargetType): void;
  (e: 'download', row: ImportRow, targetType: TargetType): void;
  (e: 'recalculate', item: ImportRow): void;
}>();

const { dataButtonColor, dataButtonLabel } = useUploadCard();

function handleUpload() {
  emit('upload', props.row, TargetType.DATA_ENTRIES);
}

function handleDownload(row: ImportRow, targetType: TargetType) {
  emit('download', row, targetType);
}

function handleRecalculate(item: ImportRow) {
  emit('recalculate', item);
}
</script>

<template>
  <UploadCard
    :title="$t('data_management_data')"
    :description="$t('data_management_data_description')"
    :row="row"
    :button-color="dataButtonColor(row)"
    :button-label="dataButtonLabel(row)"
    :is-disabled="isDisabled || row.isDisabled"
    :is-loading="row.lastDataJob?.state === IngestionState.RUNNING"
    :last-job="row.lastDataJob"
    :target-type="TargetType.DATA_ENTRIES"
    :has-recalc-button="row.hasFactors"
    :recalc-status="recalcStatus"
    :recalc-running="recalcRunning"
    @upload="handleUpload"
    @download="handleDownload"
    @recalculate="handleRecalculate"
  />
</template>
