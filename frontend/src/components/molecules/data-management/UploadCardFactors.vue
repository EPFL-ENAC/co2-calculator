<script setup lang="ts">
import { computed, inject, type ComputedRef } from 'vue';
import { useUploadCard } from 'src/composables/useUploadCard';
import { mergeLivePipelineJob } from 'src/composables/useModuleConfig';
import { useI18n } from 'vue-i18n';
import {
  TargetType,
  IngestionState,
} from 'src/stores/backofficeDataManagement';
import type { ImportRow } from 'src/stores/backofficeDataManagement';
import type { PipelineJob, PipelineProgress } from 'src/stores/pipelineStream';
import UploadCard from './UploadCard.vue';

interface Props {
  row: ImportRow;
  module?: string;
  isDisabled?: boolean;
  computedFactorRunning?: boolean;
  anyComputedFactorRunning?: boolean;
  /** Issue #1219 — module-scoped pipeline progress (null when idle). */
  pipelineProgress?: PipelineProgress | null;
  onDownload?: (row: ImportRow, targetType: TargetType) => void;
}

const props = withDefaults(defineProps<Props>(), {
  module: undefined,
  isDisabled: false,
  computedFactorRunning: false,
  anyComputedFactorRunning: false,
  pipelineProgress: null,
  onDownload: undefined,
});

const emit = defineEmits<{
  (e: 'upload', row: ImportRow, targetType: TargetType): void;
  (e: 'recalculate', item: ImportRow): void;
  (e: 'compute-factors', item: ImportRow): void;
  (e: 'abort'): void;
}>();

const { t } = useI18n();
const { factorButtonColor, factorButtonLabel } = useUploadCard();

// Live pipeline-SSE jobs keyed by job_id (provided by ``ModuleConfig``).
// See ``mergeLivePipelineJob`` — rehydrates the row spinner after page
// reload when the per-job SSE in ``useDataEntryDialog`` is gone.
const livePipelineJobsById = inject<ComputedRef<ReadonlyMap<number, PipelineJob>>>(
  'livePipelineJobsById',
  computed(() => new Map()),
);

const effectiveFactorJob = computed(() =>
  mergeLivePipelineJob(props.row.lastFactorJob, livePipelineJobsById.value),
);

const description = computed(() => {
  if (props.module === 'headcount') {
    return t('data_management_factor_headcount_description');
  }
  return t('data_management_factor_description');
});

const hasComputedFactor = computed(() => {
  return props.module === 'research-facilities';
});

function handleUpload() {
  emit('upload', props.row, TargetType.FACTORS);
}

function handleDownload(row: ImportRow, targetType: TargetType) {
  props.onDownload?.(row, targetType);
}

function handleRecalculate(item: ImportRow) {
  emit('recalculate', item);
}

function handleComputeFactors(item: ImportRow) {
  emit('compute-factors', item);
}
</script>

<template>
  <UploadCard
    :title="$t('data_management_factor')"
    :description="description"
    :show-mandatory-indicator="true"
    :row="row"
    :button-color="factorButtonColor(row)"
    :button-label="factorButtonLabel(row)"
    :is-disabled="isDisabled || row.isDisabled"
    :is-loading="effectiveFactorJob?.state === IngestionState.RUNNING"
    :last-job="effectiveFactorJob"
    :target-type="TargetType.FACTORS"
    :has-recalc-button="true"
    :pipeline-progress="pipelineProgress"
    :has-computed-factor-button="hasComputedFactor"
    :computed-factor-running="computedFactorRunning"
    :is-computed-factor-disabled="props.anyComputedFactorRunning"
    @upload="handleUpload"
    @download="handleDownload"
    @recalculate="handleRecalculate"
    @compute-factors="handleComputeFactors"
    @abort="emit('abort')"
  />
</template>
