<script setup lang="ts">
import { ref, watch, onMounted, provide } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import TempFilesBanner from 'src/components/organisms/data-management/TempFilesBanner.vue';
import { MODULES_LIST } from 'src/constant/modules';

import ModuleConfig from 'src/components/organisms/data-management/ModuleConfig.vue';
import ReductionObjectivesSection from 'src/components/organisms/data-management/ReductionObjectivesSection.vue';
import DataEntryDialog from 'src/components/organisms/data-management/DataEntryDialog.vue';

import {
  useBackofficeDataManagement,
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
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

const fetchYearConfig = async () => {
  await yearConfigStore.fetchConfig(selectedYear.value);
};

watch(
  selectedYear,
  async () => {
    try {
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
  () => yearConfigStore.loading,
  (newValue) => {
    if (newValue) {
      Loading.show({ message: $t('data_management_loading') });
    } else {
      Loading.hide();
    }
  },
);

onMounted(() => {
  // intentionally empty — loading is handled by the yearConfigStore.loading watcher
});

// ── Data-entry dialog (provided to child components like ReductionObjectivesSection) ──
const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

function openDataEntryDialog(row: ImportRow, targetType: TargetType | null) {
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
}

provide('openDataEntryDialog', openDataEntryDialog);

async function handleDialogCompleted() {
  await yearConfigStore.fetchConfig(selectedYear.value);
}
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT" />
    <div class="q-my-xl q-px-xl">
      <q-card flat bordered class="q-pa-md q-mb-xl">
        <div class="row justify-between items-center">
          <q-card-section class="row justify-between full-width q-pa-none">
            <div class="text-subtitle1">
              {{ $t('data_management_reporting_year') }}
            </div>
            <q-btn
              color="accent"
              :label="$t('data_management_sync_units_from_accred')"
              icon="sync"
              size="sm"
              :loading="backofficeDataManagement.loading"
              :disable="backofficeDataManagement.loading"
              @click="handleUnitSync"
            >
            </q-btn>
          </q-card-section>

          <q-select
            v-model="selectedYear"
            :options="availableYears"
            outlined
            dense
            class="full-width q-my-md"
          >
            <template #prepend>
              <q-icon name="event" color="accent" size="xs" />
            </template>
          </q-select>

          <div class="text-body2 text-secondary">
            {{ $t('data_management_reporting_year_hint') }}
          </div>
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

      <!-- Loading skeleton -->
      <template v-else-if="yearConfigStore.loading && !yearConfigStore.config">
        <q-skeleton type="rect" height="80px" class="q-mb-md" />
        <q-skeleton type="rect" height="200px" class="q-mb-md" />
      </template>

      <template v-if="yearConfigStore.config">
        <temp-files-banner class="q-mb-xl" />
        <template v-for="module in MODULES_LIST" :key="module">
          <ModuleConfig :module="module" :selected-year="selectedYear" />
        </template>
        <ReductionObjectivesSection :selected-year="selectedYear" />
      </template>

      <q-btn
        icon="calendar_month"
        color="accent"
        :label="$t('open_year_for_users')"
        class="text-weight-medium text-capitalize q-mt-md"
        :disable="yearConfigStore.anyModuleIncomplete"
      >
        <q-tooltip v-if="yearConfigStore.anyModuleIncomplete">
          {{ $t('data_management_open_year_disabled_tooltip') }}
        </q-tooltip>
      </q-btn>
    </div>

    <data-entry-dialog
      v-model="showDataEntryDialog"
      :row="dialogCurrentRow || ({} as ImportRow)"
      :year="selectedYear"
      :target-type="dialogTargetType ?? TargetType.DATA_ENTRIES"
      @completed="handleDialogCompleted"
      @progressing="handleDialogCompleted"
    />
  </q-page>
</template>
