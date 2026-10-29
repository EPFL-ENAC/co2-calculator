<script setup lang="ts">
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
  /** Issue #1219 — module-scoped pipeline progress (null when idle). */
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

const { dataButtonColor, dataButtonLabel } = useUploadCard();

// Live pipeline-SSE jobs keyed by job_id (provided by ``ModuleConfig``).
// Empty map when no pipeline is active OR when this card is rendered
// outside a ``ModuleConfig`` (e.g. in a fixture / preview).  See
// ``mergeLivePipelineJob`` for the overlay rationale.
const livePipelineJobsById = inject<
  ComputedRef<ReadonlyMap<number, PipelineJob>>
>(
  'livePipelineJobsById',
  computed(() => new Map()),
);

const effectiveDataJob = computed(() =>
  mergeLivePipelineJob(props.row.lastDataJob, livePipelineJobsById.value),
);

function handleUpload(_row: ImportRow, _targetType: TargetType, file?: File) {
  emit('upload', props.row, TargetType.DATA_ENTRIES, file);
}

function handleDownload(row: ImportRow, targetType: TargetType) {
  props.onDownload?.(row, targetType);
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
    :is-loading="effectiveDataJob?.state === IngestionState.RUNNING"
    :last-job="effectiveDataJob"
    :api-job="row.lastApiDataJob"
    :target-type="TargetType.DATA_ENTRIES"
    :pipeline-progress="pipelineProgress"
    @upload="handleUpload"
    @download="handleDownload"
    @abort="emit('abort')"
  />
</template>
