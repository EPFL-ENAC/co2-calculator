<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useBackofficeStore } from 'src/stores/backoffice';

const backofficeStore = useBackofficeStore();

const availableYears = computed(() => backofficeStore.availableYearsList);
const latestYear = computed(() => backofficeStore.latestYear);

const yearOptions = computed(() =>
  availableYears.value.map((year) => ({ label: year, value: year })),
);

const years = ref<string[]>([]);

const emit = defineEmits<{
  (e: 'update:years', years: string[]): void;
}>();

// Initialize with latest year when available
watch(
  latestYear,
  (newLatestYear) => {
    if (newLatestYear && years.value.length === 0) {
      years.value = [newLatestYear];
    }
  },
  { immediate: true },
);

watch(
  years,
  (newYears) => {
    if (newYears.length === 0) {
      // Fallback to latest year or default
      years.value = [latestYear.value || '2026'];
      return;
    }
    emit('update:years', newYears);
  },
  { immediate: true },
);

onMounted(async () => {
  await backofficeStore.getAvailableYears();
  if (latestYear.value && years.value.length === 0) {
    years.value = [latestYear.value];
  }
});
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
