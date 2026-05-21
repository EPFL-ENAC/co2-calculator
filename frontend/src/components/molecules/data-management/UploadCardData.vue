<script setup lang="ts">
import { computed, inject, type ComputedRef } from 'vue';
import { useUploadCard } from 'src/composables/useUploadCard';
import { mergeLivePipelineJob } from 'src/composables/useModuleConfig';
import {
  TargetType,
  IngestionState,
} from 'src/stores/backofficeDataManagement';
import type { ImportRow } from 'src/stores/backofficeDataManagement';
import type { RecalculationStatusEntry } from 'src/stores/yearConfig';
import type { PipelineJob, PipelineProgress } from 'src/stores/pipelineStream';
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
    :is-loading="effectiveDataJob?.state === IngestionState.RUNNING"
    :last-job="effectiveDataJob"
    :api-job="row.lastApiDataJob"
    :target-type="TargetType.DATA_ENTRIES"
    :has-recalc-button="row.hasFactors"
    :recalc-status="recalcStatus"
    :recalc-running="recalcRunning"
    :pipeline-progress="pipelineProgress"
    @upload="handleUpload"
    @download="handleDownload"
    @recalculate="handleRecalculate"
    @abort="emit('abort')"
  />
</template>
