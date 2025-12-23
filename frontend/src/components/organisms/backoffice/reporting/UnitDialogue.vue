<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useBackofficeStore } from 'src/stores/backoffice';
import { Module, getBackendModuleName } from 'src/constant/modules';
import { MODULE_STATES, ModuleState } from 'src/constant/moduleStates';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import ReportExport from './ReportExport.vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

const backofficeStore = useBackofficeStore();

const props = defineProps<{
  modelValue: boolean;
  unitId: string | number;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
}>();

const { t } = useI18n();

interface ModuleCompletion {
  status: ModuleState;
  outlier_values: number;
}

const selectedYearInDialog = ref<string>('');

const unitData = computed(() => backofficeStore.selectedUnit);
const loading = computed(() => backofficeStore.unitLoading);
const error = computed(() => {
  const errors = backofficeStore.unitErrors;
  return errors.length > 0 ? errors[0].message : null;
});

// Get available years from unit data
const availableYears = computed(() => {
  if (!unitData.value) return [];

  const completion = unitData.value.completion;

  // Check if it's year-based structure
  const completionKeys = Object.keys(completion);
  const isYearBased = completionKeys.some(
    (key) => typeof key === 'string' && /^\d{4}$/.test(key),
  );

  if (isYearBased) {
    const years = completionKeys
      .filter((key) => /^\d{4}$/.test(key))
      .sort()
      .reverse(); // Sort descending (latest first)

    return years;
  }

  return [];
});

// Initialize selected year to latest when years are available
watch(
  availableYears,
  (years) => {
    if (years.length > 0) {
      // Always set to latest year (first in descending sorted array)
      // Only update if current value is not in the available years or is empty
      if (
        !selectedYearInDialog.value ||
        !years.includes(selectedYearInDialog.value)
      ) {
        selectedYearInDialog.value = years[0];
      }
    }
  },
  { immediate: true },
);

// Also watch unitData to set latest year when data loads
watch(
  () => unitData.value,
  (newData) => {
    if (newData) {
      const years = availableYears.value;
      if (years.length > 0) {
        selectedYearInDialog.value = years[0];
      }
    } else {
      selectedYearInDialog.value = '';
    }
  },
  { immediate: true },
);

const dialogModel = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
});

async function fetchUnit() {
  if (!props.unitId) return;

  const data = await backofficeStore.getUnit(props.unitId);

  // Set the selected year after data loads
  if (data && availableYears.value.length > 0) {
    selectedYearInDialog.value = availableYears.value[0];
  }
}

// Watch for dialog opening to fetch unit data
watch(
  () => props.modelValue,
  (isOpen) => {
    if (isOpen && props.unitId) {
      // Reset selected year when dialog opens
      selectedYearInDialog.value = '';
      fetchUnit();
    } else if (!isOpen) {
      // Clear data when dialog closes
      backofficeStore.reset();
      selectedYearInDialog.value = '';
    }
  },
);

interface ModuleRow {
  module: Module;

  status: string;
  statusColor: string;
  statusTextColor?: string;
  outlierValues: number;
}

// Get completion data for selected year
const completionForSelectedYear = computed(() => {
  if (!unitData.value) return null;

  const completion = unitData.value.completion;
  const selectedYear = selectedYearInDialog.value; // Explicitly track this dependency

  // Check if it's year-based structure (keys are year strings like "2024", "2025")
  const completionKeys = Object.keys(completion);
  const isYearBased = completionKeys.some(
    (key) => typeof key === 'string' && /^\d{4}$/.test(key),
  );

  if (isYearBased) {
    // Get the year to use - prefer selected year, fallback to latest available
    let yearKey = selectedYear;
    if (!yearKey && availableYears.value.length > 0) {
      yearKey = availableYears.value[0];
    }

    if (yearKey) {
      // Access the year data directly
      const yearData = (
        completion as Record<string, Record<string, ModuleCompletion>>
      )[yearKey];

      if (
        yearData &&
        typeof yearData === 'object' &&
        !Array.isArray(yearData)
      ) {
        // Verify it's the expected structure (module -> completion data)
        return yearData as Record<string, ModuleCompletion>;
      }
    }
    return null;
  }

  // Flat structure (old format) - return as-is
  return completion as Record<string, ModuleCompletion>;
});

// Calculate completion counts for selected year
const completionCountsForYear = computed(() => {
  const yearData = completionForSelectedYear.value;
  if (!yearData) {
    return { validated: 0, in_progress: 0, default: 0 };
  }

  const counts = { validated: 0, in_progress: 0, default: 0 };
  Object.values(yearData).forEach((moduleData) => {
    const status = moduleData?.status || 'default';
    if (status === 'validated') {
      counts.validated += 1;
    } else if (status === 'in-progress') {
      counts.in_progress += 1;
    } else {
      counts.default += 1;
    }
  });
  return counts;
});

const moduleRows = computed<ModuleRow[]>(() => {
  if (!unitData.value || !completionForSelectedYear.value) {
    return [];
  }

  const yearData = completionForSelectedYear.value;

  return MODULE_CARDS.map((card) => {
    const backendModuleName = getBackendModuleName(card.module);
    const moduleData = yearData[backendModuleName];

    // Extract status and outlier_values from module data
    const moduleStatus = moduleData?.status || 'default';
    const outlierCount = moduleData?.outlier_values || 0;
    let status;
    let statusColor;
    const statusTextColor = 'white';

    if (moduleStatus === 'validated') {
      status = t(MODULE_STATES.Validated);
      statusColor = 'green';
    } else if (moduleStatus === 'in-progress') {
      status = t(MODULE_STATES.InProgress);
      statusColor = 'orange';
    } else {
      status = t(MODULE_STATES.Default);
      statusColor = 'grey';
    }

    return {
      module: card.module,
      status,
      statusColor,
      statusTextColor,
      outlierValues: outlierCount,
    };
  });
});

const columns = computed<QTableColumn[]>(() => [
  {
    name: 'module',
    label: t('backoffice_reporting_row_module_label'),
    field: 'module',
    align: 'left',
    sortable: true,
  },
  {
    name: 'status',
    label: t('backoffice_reporting_row_status_label'),
    field: 'status',
    align: 'left',
    sortable: true,
  },
  {
    name: 'outlier_values',
    label: t('backoffice_reporting_row_outlier_values_label'),
    field: 'outlierValues',
    align: 'left',
    sortable: true,
    sort: (a: number, b: number, rowA: ModuleRow, rowB: ModuleRow) => {
      return rowA.outlierValues - rowB.outlierValues;
    },
  },
]);
</script>

<template>
  <q-dialog v-model="dialogModel" class="modal-grid">
    <q-card class="column" :class="`modal modal--lg`">
      <q-card-section class="flex justify-between items-center flex-shrink">
        <div class="text-h4 text-weight-medium">{{ unitData?.unit }}</div>
        <q-btn
          v-close-popup
          flat
          size="md"
          icon="o_close"
          color="grey-6"
          class="text-weight-medium"
        />
      </q-card-section>
      <q-separator />
      <q-card-section>
        <div v-if="loading" class="flex justify-center q-pa-lg">
          <q-spinner color="accent" size="3em" />
        </div>
        <div v-else-if="error" class="text-negative q-pa-md">
          {{ error }}
        </div>
        <div v-else-if="unitData">
          <!-- Year selector dropdown (show if years available) - at the top -->
          <div v-if="availableYears.length > 0" class="q-mb-lg">
            <q-select
              v-model="selectedYearInDialog"
              :options="availableYears"
              outlined
              dense
              :label="t('backoffice_reporting_select_year')"
              class="full-width"
              :disable="availableYears.length === 1"
              emit-value
              map-options
            >
              <template #prepend>
                <q-icon name="o_calendar_month" color="accent" size="xs" />
              </template>
            </q-select>
          </div>

          <!-- Completion counts for selected year -->
          <div class="grid-3-col q-mb-lg">
            <div class="container">
              <div class="q-mb-xs">
                <span class="text-h2 text-weight-medium">{{
                  completionCountsForYear.validated
                }}</span>
              </div>
              <q-icon name="check" color="green" size="xs" />
              <span class="text-body2 q-ml-sm">{{
                t(MODULE_STATES.Validated)
              }}</span>
            </div>
            <div class="container">
              <div class="q-mb-xs">
                <span class="text-h2 text-weight-medium">{{
                  completionCountsForYear.in_progress
                }}</span>
              </div>
              <q-icon name="hourglass_empty" color="orange" size="xs" />
              <span class="text-body2 q-ml-sm">{{
                t(MODULE_STATES.InProgress)
              }}</span>
            </div>
            <div class="container">
              <div class="q-mb-xs">
                <span class="text-h2 text-weight-medium">{{
                  completionCountsForYear.default
                }}</span>
              </div>
              <q-icon name="check_box_outline_blank" color="grey-6" size="xs" />
              <span class="text-body2 q-ml-sm">{{
                t(MODULE_STATES.Default)
              }}</span>
            </div>
          </div>

          <!-- Modules table for selected year -->
          <div
            v-if="!loading && !error && unitData"
            class="flex justify-between q-mt-lg q-mb-sm"
          >
            <span class="text-body1 text-weight-medium">{{
              t('backoffice_reporting_modules_label', {
                count: moduleRows.length,
              })
            }}</span>
          </div>
          <q-table
            v-if="!loading && !error && unitData"
            class="co2-table border"
            flat
            :rows="moduleRows"
            :columns="columns"
            row-key="module"
            hide-pagination
            :rows-per-page="moduleRows.length"
            :pagination="{ rowsPerPage: moduleRows.length }"
          >
            <template #body="{ row, rowIndex }">
              <q-tr
                class="q-tr--no-hover"
                :class="{
                  'bg-grey-1': rowIndex % 2 === 1,
                }"
              >
                <!-- Module -->
                <q-td key="module">
                  <div class="flex items-center q-gutter-sm">
                    <ModuleIcon :name="row.module" color="accent" size="md" />
                    <span class="text-body2 text-weight-medium">{{
                      t(row.module)
                    }}</span>
                  </div>
                </q-td>

                <!-- Status -->
                <q-td key="status">
                  <q-badge
                    :color="row.statusColor"
                    :text-color="row.statusTextColor"
                    :label="row.status"
                  />
                </q-td>

                <!-- Outlier Values -->
                <q-td key="outlier_values">
                  <q-badge
                    v-if="row.outlierValues > 0"
                    color="red"
                    :label="`${row.outlierValues} ${t('backoffice_reporting_row_outlier_values_label')}`"
                    class="text-white"
                  />
                  <span v-else class="text-grey-6">—</span>
                </q-td>
              </q-tr>
            </template>
          </q-table>

          <ReportExport />
        </div>
      </q-card-section>
    </q-card>
  </q-dialog>
</template>
