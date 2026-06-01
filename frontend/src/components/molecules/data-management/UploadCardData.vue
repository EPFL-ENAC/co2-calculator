<script setup lang="ts">
import { useUploadCard } from 'src/composables/useUploadCard';
import {
  TargetType,
  IngestionState,
} from 'src/stores/backofficeDataManagement';
import type { ImportRow } from 'src/stores/backofficeDataManagement';
import type { RecalculationStatusEntry } from 'src/stores/yearConfig';
import type { PipelineProgress } from 'src/stores/pipelineStream';
import UploadCard from './UploadCard.vue';

interface Props {
  row: ImportRow;
  isDisabled?: boolean;
  recalcRunning?: boolean;
  recalcStatus?: RecalculationStatusEntry;
  /** Issue #1219 — module-scoped pipeline progress (null when idle). */
  pipelineProgress?: PipelineProgress | null;
  onDownload?: (row: ImportRow, targetType: TargetType) => void;
}

const props = withDefaults(defineProps<Props>(), {
  isDisabled: false,
  recalcRunning: false,
  recalcStatus: undefined,
  pipelineProgress: null,
  onDownload: undefined,
});

const emit = defineEmits<{
  (e: 'upload', row: ImportRow, targetType: TargetType): void;
  (e: 'recalculate', item: ImportRow): void;
  (e: 'cancel', jobId: number): void;
}>();

const { dataButtonColor, dataButtonLabel } = useUploadCard();

function handleUpload() {
  emit('upload', props.row, TargetType.DATA_ENTRIES);
}

function handleDownload(row: ImportRow, targetType: TargetType) {
  props.onDownload?.(row, targetType);
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
    :api-job="row.lastApiDataJob"
    :target-type="TargetType.DATA_ENTRIES"
    :has-recalc-button="row.hasFactors"
    :recalc-status="recalcStatus"
    :recalc-running="recalcRunning"
    :pipeline-progress="pipelineProgress"
    @upload="handleUpload"
    @download="handleDownload"
    @recalculate="handleRecalculate"
    @cancel="emit('cancel', $event)"
  />
</template>
