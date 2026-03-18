<script setup lang="ts">
import { ref } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import AnnualDataImport from 'src/components/organisms/data-management/AnnualDataImport.vue';
import ModulesConfig from 'src/components/organisms/data-management/ModulesConfig.vue';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';

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
const { t: $t } = useI18n();

// Fetch sync jobs when year changes
const fetchSyncJobs = async () => {
  await backofficeDataManagement.fetchSyncJobsByYear(selectedYear.value);
};

// Watch for year changes and fetch sync jobs
import { watch } from 'vue';
watch(selectedYear, fetchSyncJobs, { immediate: true });

// Handle unit sync from Accred API
const handleUnitSync = async () => {
  try {
    await backofficeDataManagement.syncUnitsFromAccred();

    Notify.create({
      type: 'info',
      message: $t('data_management_unit_sync_started'),
      caption: $t('data_management_unit_sync_started_caption'),
    });

    // Show success notification after a delay (simple approach without polling)
    setTimeout(() => {
      Notify.create({
        type: 'positive',
        message: $t('data_management_unit_sync_success'),
        caption: $t('data_management_unit_sync_success_caption'),
      });
    }, 5000);
  } catch (error: unknown) {
    const errorMessage =
      error instanceof Error ? error.message : 'Unknown error';
    Notify.create({
      type: 'negative',
      message: $t('data_management_unit_sync_error'),
      caption: errorMessage || $t('data_management_unit_sync_error_caption'),
    });
  }
};
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />

    <div class="q-my-xl q-px-xl">
      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="row justify-between items-center">
          <!-- Block A: Title, Select, and Hint -->
          <div>
            <div class="text-subtitle1">
              {{ $t('data_management_reporting_year') }}
            </div>
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

            <div class="q-mt-sm text-body2 text-secondary">
              {{ $t('data_management_reporting_year_hint') }}
            </div>
          </div>

          <!-- Block B: Sync Button -->
          <q-btn
            color="primary"
            :label="$t('data_management_sync_units_from_accred')"
            icon="sync"
            :loading="backofficeDataManagement.loading"
            :disable="backofficeDataManagement.loading"
            @click="handleUnitSync"
          >
          </q-btn>
        </div>
      </q-card>
      <annual-data-import :year="selectedYear" />
      <modules-config :year="selectedYear" />
    </div>
  </q-page>
</template>
