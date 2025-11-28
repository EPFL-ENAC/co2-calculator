<script setup lang="ts">
import { ref, watch } from 'vue';

const yearOptions = ref([
  { label: '2024', value: '2024' },
  { label: '2025', value: '2025' },
  { label: '2026', value: '2026' },
]);

const years = ref<string[]>(['2026']);

const emit = defineEmits<{
  (e: 'update:years', years: string[]): void;
}>();

watch(
  years,
  (newYears) => {
    if (newYears.length === 0) {
      years.value = ['2026'];
      return;
    }
    emit('update:years', newYears);
  },
  { immediate: true },
);
</script>

<template>
  <div class="q-mt-lg">
    <q-select
      v-model="years"
      :options="yearOptions"
      option-value="value"
      option-label="label"
      multiple
      use-chips
      outlined
      label="Year"
      class="full-width text-weight-bold"
      style="flex-grow: 1"
    >
      <template #prepend>
        <q-icon name="o_calendar_month" color="accent" size="sm" />
      </template>
    </q-select>
  </div>
</template>
