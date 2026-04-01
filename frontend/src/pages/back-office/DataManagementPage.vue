<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import AnnualDataImport from 'src/components/organisms/data-management/AnnualDataImport.vue';
import ModulesConfigNew from 'src/components/organisms/data-management/ModulesConfigNew.vue';
import ReductionObjectives from 'src/components/organisms/data-management/ReductionObjectives.vue';
import { useBackofficeDataManagement } from 'src/stores/backofficeDataManagement';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { Notify, Loading } from 'quasar';
import { useI18n } from 'vue-i18n';

// TODO: fix the available years dynamically
const MIN_YEARS = 2024;
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
const yearConfigStore = useYearConfigStore();
const { t: $t } = useI18n();

const fetchSyncJobs = async () => {
  await backofficeDataManagement.fetchLatestSyncJobsByYear(selectedYear.value);
};

const fetchYearConfig = async () => {
  await yearConfigStore.fetchConfig(selectedYear.value);
};

watch(
  selectedYear,
  async () => {
    try {
      await fetchSyncJobs();
      await fetchYearConfig();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to load year data';
      Notify.create({ type: 'negative', message: msg });
    }
  },
  { immediate: true },
);

const handleCreateYear = async () => {
  try {
    await yearConfigStore.createConfig(selectedYear.value);
    Notify.create({
      type: 'positive',
      message: $t('data_management_year_created', { year: selectedYear.value }),
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    Notify.create({ type: 'negative', message: msg });
  }
};

const handleToggleStarted = async () => {
  if (!yearConfigStore.config) return;
  const newState = !yearConfigStore.config.is_started;
  try {
    await yearConfigStore.updateConfig(selectedYear.value, {
      is_started: newState,
    });
    Notify.create({
      type: 'positive',
      message: newState
        ? $t('data_management_year_enabled', { year: selectedYear.value })
        : $t('data_management_year_disabled', { year: selectedYear.value }),
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    Notify.create({ type: 'negative', message: msg });
  }
};

const handleUnitSync = async () => {
  try {
    await backofficeDataManagement.syncUnitsFromAccred(selectedYear.value);

    Notify.create({
      type: 'info',
      message: $t('data_management_unit_sync_started'),
      caption: $t('data_management_unit_sync_started_caption'),
    });

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

watch(
  () => backofficeDataManagement.loading,
  (newValue) => {
    if (newValue) {
      Loading.show({ message: $t('data_management_loading') });
    } else {
      Loading.hide();
    }
  },
);

onMounted(() => {});
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />

    <div class="q-my-xl q-px-xl">
      <!-- Year selector + sync button -->
      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="row justify-between items-center">
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

          <q-btn
            color="primary"
            :label="$t('data_management_sync_units_from_accred')"
            icon="sync"
            :loading="backofficeDataManagement.loading"
            :disable="backofficeDataManagement.loading"
            @click="handleUnitSync"
          />
        </div>
      </q-card>

      <!-- Startup: no configuration exists yet -->
      <q-card
        v-if="yearConfigStore.notFound && !yearConfigStore.loading"
        flat
        bordered
        class="q-pa-xl q-mb-xl text-center"
      >
        <q-icon
          name="calendar_today"
          size="64px"
          color="grey-5"
          class="q-mb-md"
        />
        <div class="text-h6 q-mb-sm">
          {{
            $t('data_management_year_not_configured', { year: selectedYear })
          }}
        </div>
        <div class="text-body2 text-secondary q-mb-lg">
          {{ $t('data_management_year_not_configured_hint') }}
        </div>
        <q-btn
          color="primary"
          icon="add"
          :label="$t('data_management_create_year', { year: selectedYear })"
          :loading="yearConfigStore.loading"
          @click="handleCreateYear"
        />
      </q-card>

      <!-- Configuration exists: show is_started status banner + all sections -->
      <template v-else-if="yearConfigStore.config && !yearConfigStore.loading">
        <!-- Status banner -->
        <q-banner
          :class="
            yearConfigStore.config.is_started
              ? 'bg-positive text-white'
              : 'bg-warning text-dark'
          "
          rounded
          class="q-mb-lg"
        >
          <template #avatar>
            <q-icon
              :name="
                yearConfigStore.config.is_started
                  ? 'check_circle'
                  : 'pause_circle'
              "
              size="sm"
            />
          </template>
          <span class="text-weight-medium">
            {{
              yearConfigStore.config.is_started
                ? $t('data_management_year_status_enabled', {
                    year: selectedYear,
                  })
                : $t('data_management_year_status_disabled', {
                    year: selectedYear,
                  })
            }}
          </span>
          <template #action>
            <q-btn
              flat
              :label="
                yearConfigStore.config.is_started
                  ? $t('data_management_year_disable')
                  : $t('data_management_year_enable')
              "
              :loading="yearConfigStore.loading"
              @click="handleToggleStarted"
            />
          </template>
        </q-banner>

        <annual-data-import :year="selectedYear" />
        <modules-config-new :year="selectedYear" />
        <reduction-objectives :year="selectedYear" />
      </template>

      <!-- Loading skeleton -->
      <template v-else-if="yearConfigStore.loading">
        <q-skeleton type="rect" height="80px" class="q-mb-md" />
        <q-skeleton type="rect" height="200px" class="q-mb-md" />
      </template>
    </div>
  </q-page>
</template>
