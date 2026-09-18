<script setup lang="ts">
import { matFileUpload } from '@quasar/extras/material-icons';
import { computed, inject, type ComputedRef } from 'vue';
import { useUploadCard } from '@/composables/useUploadCard';
import { mergeLivePipelineJob } from '@/composables/useModuleConfig';
import { TargetType, IngestionState } from '@/stores/backofficeDataManagement';
import type { ImportRow } from '@/stores/backofficeDataManagement';
import type { PipelineJob, PipelineProgress } from '@/stores/pipelineStream';
import UploadCard from './UploadCard.vue';

interface Props {
  row: ImportRow;
  isDisabled?: boolean;
  pipelineProgress?: PipelineProgress | null;
  onDownload?: (row: ImportRow, targetType: TargetType) => void;
}

const props = withDefaults(defineProps<Props>(), {
  isDisabled: false,
  pipelineProgress: null,
  onDownload: undefined,
});

const emit = defineEmits<{
  (e: 'upload', row: ImportRow, targetType: TargetType, file?: File): void;
  (e: 'abort'): void;
}>();

const { referenceButtonColor, referenceButtonLabel } = useUploadCard();

// Live pipeline-SSE jobs keyed by job_id (provided by ``ModuleConfig``).
// See ``mergeLivePipelineJob`` — rehydrates the row spinner after page
// reload when the per-job SSE in ``useDataEntryDialog`` is gone.
const livePipelineJobsById = inject<
  ComputedRef<ReadonlyMap<number, PipelineJob>>
>(
  'livePipelineJobsById',
  computed(() => new Map()),
);

const effectiveReferenceJob = computed(() =>
  mergeLivePipelineJob(props.row.lastReferenceJob, livePipelineJobsById.value),
);

function handleUpload(_row: ImportRow, _targetType: TargetType, file?: File) {
  emit('upload', props.row, TargetType.REFERENCE_DATA, file);
}

function handleDownload(row: ImportRow, targetType: TargetType) {
  props.onDownload?.(row, targetType);
}
</script>

<template>
  <UploadCard
    :title="$t('data_management_references')"
    :description="$t('data_management_references_description')"
    :description-subtext="row.other ? $t(row.other) : undefined"
    :show-mandatory-indicator="true"
    :row="row"
    :button-color="referenceButtonColor(row)"
    :button-label="referenceButtonLabel(row)"
    :button-icon="matFileUpload"
    :is-disabled="isDisabled || row.isDisabled"
    :is-loading="effectiveReferenceJob?.state === IngestionState.RUNNING"
    :last-job="effectiveReferenceJob"
    :target-type="TargetType.REFERENCE_DATA"
    :pipeline-progress="pipelineProgress"
    @upload="handleUpload"
    @download="handleDownload"
    @abort="emit('abort')"
  />
</template>
