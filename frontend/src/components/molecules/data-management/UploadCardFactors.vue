<script setup lang="ts">
import { computed } from 'vue';
import { useUploadCard } from 'src/composables/useUploadCard';
import { useI18n } from 'vue-i18n';
import {
  TargetType,
  IngestionState,
} from 'src/stores/backofficeDataManagement';
import type { ImportRow } from 'src/stores/backofficeDataManagement';
import UploadCard from './UploadCard.vue';

interface Props {
  row: ImportRow;
  module?: string;
  isDisabled?: boolean;
  computedFactorRunning?: boolean;
  anyComputedFactorRunning?: boolean;
  onDownload?: (row: ImportRow, targetType: TargetType) => void;
}

const props = withDefaults(defineProps<Props>(), {
  module: undefined,
  isDisabled: false,
  computedFactorRunning: false,
  anyComputedFactorRunning: false,
  onDownload: undefined,
});

const emit = defineEmits<{
  (e: 'upload', row: ImportRow, targetType: TargetType): void;
  (e: 'recalculate', item: ImportRow): void;
  (e: 'compute-factors', item: ImportRow): void;
}>();

const { t } = useI18n();
const { factorButtonColor, factorButtonLabel } = useUploadCard();

const description = computed(() => {
  if (props.module === 'headcount') {
    return t('data_management_factor_headcount_description');
  }
  return t('data_management_factor_description');
});

const hasComputedFactor = computed(() => {
  return props.module === 'research_facilities';
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
    :is-loading="row.lastFactorJob?.state === IngestionState.RUNNING"
    :last-job="row.lastFactorJob"
    :target-type="TargetType.FACTORS"
    :has-recalc-button="true"
    :has-computed-factor-button="hasComputedFactor"
    :computed-factor-running="computedFactorRunning"
    :is-computed-factor-disabled="props.anyComputedFactorRunning"
    @upload="handleUpload"
    @download="handleDownload"
    @recalculate="handleRecalculate"
    @compute-factors="handleComputeFactors"
  />
</template>
