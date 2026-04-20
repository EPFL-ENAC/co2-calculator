<script setup lang="ts">
import { MODULE_SUBMODULES } from 'src/constant/backoffice-module-config';
import SubmoduleItem from 'src/components/molecules/data-management/SubmoduleItem.vue';
import {
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import type { SubmoduleConfig } from 'src/constant/backoffice-module-config';

interface Props {
  module: string;
  selectedYear: number;
}

defineProps<Props>();
const emit = defineEmits<{
  (e: 'dataUpload', row: ImportRow, targetType: TargetType): void;
  (e: 'factorUpload', row: ImportRow, targetType: TargetType): void;
  (e: 'referenceCompleted'): void;
  (e: 'referenceProgressing'): void;
  (e: 'download', row: ImportRow, targetType: TargetType): void;
  (e: 'recalculate', sub: SubmoduleConfig): void;
  (e: 'computeFactors', sub: SubmoduleConfig): void;
}>();
</script>

<template>
  <SubmoduleItem
    v-for="submodule in MODULE_SUBMODULES[module] ?? []"
    :key="submodule.key"
    :submodule="submodule"
    :selected-year="selectedYear"
    @data-upload="(row) => emit('dataUpload', row, TargetType.DATA_ENTRIES)"
    @factor-upload="(row) => emit('factorUpload', row, TargetType.FACTORS)"
    @reference-completed="() => emit('referenceCompleted')"
    @reference-progressing="() => emit('referenceProgressing')"
    @download="(row, targetType) => emit('download', row, targetType)"
    @recalculate="(sub) => emit('recalculate', sub)"
    @compute-factors="(sub) => emit('computeFactors', sub)"
  />
</template>

<style scoped></style>
