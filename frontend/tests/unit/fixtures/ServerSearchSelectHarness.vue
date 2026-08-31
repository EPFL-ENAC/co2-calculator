<script setup lang="ts">
import { ref } from 'vue';
import ServerSearchSelectField from '@/components/molecules/ServerSearchSelectField.vue';

const props = defineProps<{
  moduleType: string;
  submoduleType: string;
  year: number;
  initialOption?: { value: string; label: string } | null;
}>();

const model = ref<string | number | null>(null);
</script>

<template>
  <ServerSearchSelectField
    v-model="model"
    :module-type="props.moduleType"
    :submodule-type="props.submoduleType"
    :year="props.year"
    :initial-option="props.initialOption ?? null"
    label="code"
  />
  <div data-testid="selected">{{ model ?? '' }}</div>
</template>
