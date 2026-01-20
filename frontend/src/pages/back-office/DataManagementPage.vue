<script setup lang="ts">
import { ref } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import AnnualDataImport from 'src/components/organisms/data-management/AnnualDataImport.vue';
import ModulesConfig from 'src/components/organisms/data-management/ModulesConfig.vue';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';

// TODO: fix the available years dynamically
const MIN_YEARS = 2025;
const availableYears = ref<number[]>([]);
const currentYear = new Date().getFullYear();
if (currentYear > MIN_YEARS) {
  for (let year = MIN_YEARS; year < currentYear; year++) {
    availableYears.value.push(year);
  }
}
const selectedYear = ref<number>(
  availableYears.value[availableYears.value.length - 1],
);

const backofficeDataManagement = useBackofficeDataManagement();

// Fetch sync jobs when year changes
const fetchSyncJobs = async () => {
  await backofficeDataManagement.fetchSyncJobsByYear(selectedYear.value);
};

// Watch for year changes and fetch sync jobs
import { watch } from 'vue';
watch(selectedYear, fetchSyncJobs, { immediate: true });
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />

    <div class="q-my-xl q-px-xl">
      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="text-h5">{{ $t('data_management_reporting_year') }}</div>
        <q-select
          v-model="selectedYear"
          :options="availableYears"
          outlined
          dense
          class="q-my-md"
        >
          <template #prepend>
            <q-icon name="event" color="accent" size="xs" />
          </template>
        </q-select>
        <div>
          {{ $t('data_management_reporting_year_hint') }}
        </div>
      </q-card>
      <annual-data-import :year="selectedYear" />
      <modules-config :year="selectedYear" />
    </div>
  </q-page>
</template>
