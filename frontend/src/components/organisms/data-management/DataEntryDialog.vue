<script setup lang="ts">
import DataEntryDialogContent from '@/components/molecules/data-management/DataEntryDialogContent.vue';
import type {
  SyncJobResponse,
  ImportRow,
} from '@/stores/backofficeDataManagement';
import { TargetType } from '@/stores/backofficeDataManagement';

interface Props {
  modelValue: boolean;
  row: ImportRow;
  year: number;
  targetType: TargetType;
  dropFile?: File | null;
}

withDefaults(defineProps<Props>(), { dropFile: null });
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
    :drop-file="dropFile"
    @update:model-value="emit('update:modelValue', $event)"
    @completed="(job) => emit('completed', job)"
    @progressing="(job) => emit('progressing', job)"
  />
</template>

<style scoped></style>
