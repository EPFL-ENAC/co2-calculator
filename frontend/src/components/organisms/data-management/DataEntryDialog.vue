<script setup lang="ts">
import DataEntryDialogContent from 'src/components/molecules/data-management/DataEntryDialogContent.vue';
import type {
  SyncJobResponse,
  ImportRow,
} from 'src/stores/backofficeDataManagement';
import { TargetType } from 'src/stores/backofficeDataManagement';

interface Props {
  modelValue: boolean;
  row: ImportRow;
  year: number;
  targetType: TargetType;
}

defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'completed', job: SyncJobResponse): void;
  (e: 'progressing', job: SyncJobResponse): void;
}>();
</script>

<template>
  <DataEntryDialogContent
    :model-value="modelValue"
    :row="row"
    :year="year"
    :target-type="targetType"
    @update:model-value="emit('update:modelValue', $event)"
    @completed="(job) => emit('completed', job)"
    @progressing="(job) => emit('progressing', job)"
  />
</template>

<style scoped></style>
