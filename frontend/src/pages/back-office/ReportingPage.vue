<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import type { Module } from 'src/constant/modules';
import { MODULE_STATES, type ModuleState } from 'src/constant/moduleStates';
import { useBackofficeStore } from 'src/stores/backoffice';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import ModuleSelector, {
  type ModuleStateData,
} from 'src/components/organisms/backoffice/reporting/ModuleSelector.vue';
import ReportingStatCards from 'src/components/organisms/backoffice/reporting/ReportingStatCards.vue';
import ReportingStatCardUnit from 'src/components/organisms/backoffice/reporting/ReportingStatCardUnit.vue';
import ReportingYear from 'src/components/organisms/backoffice/reporting/ReportingYear.vue';
import ReportingFilters from 'src/components/organisms/backoffice/reporting/ReportingFilters.vue';
import UnitsTable from 'src/components/organisms/backoffice/reporting/UnitsTable.vue';
import ReportExport from 'src/components/organisms/backoffice/reporting/ReportExport.vue';
import UnitDialogue from 'src/components/organisms/backoffice/reporting/UnitDialogue.vue';
import CompletionRateBar from 'src/components/organisms/backoffice/reporting/CompletionRateBar.vue';
import ModuleCarbonFootprintChart from 'src/components/charts/results/ModuleCarbonFootprintChart.vue';
import CarbonFootPrintPerPersonChart from 'src/components/charts/results/CarbonFootPrintPerPersonChart.vue';
import EmissionBreakdownChart from 'src/components/charts/EmissionBreakdownChart.vue';
import { useRouter } from 'vue-router';
const backofficeStore = useBackofficeStore();

const router = useRouter();
const moduleStates = ref<Map<Module, ModuleStateData>>(new Map());

const allStatesSelected = computed(() => {
  const allStates = Object.values(MODULE_STATES);
  return MODULE_CARDS.every((card) => {
    const data = moduleStates.value.get(card.module);
    return data && data.states.length === allStates.length;
  });
});

async function toggleSelectAll(shouldSelectAll: boolean) {
  const allStates = Object.values(MODULE_STATES);

  // Create a new Map to ensure reactivity
  const newModuleStates = new Map<Module, ModuleStateData>();
  MODULE_CARDS.forEach((card) => {
    newModuleStates.set(card.module, {
      module: card.module,
      states: shouldSelectAll ? [...allStates] : [],
    });
  });
  moduleStates.value = newModuleStates;

  // Wait for computed property to update before fetching
  await nextTick();
  // Always fetch units after toggling - this ensures the table refreshes
  await fetchUnits();
}

const selectedYears = ref<string[]>(['2026']); // Default to latest year

// Track selected hierarchy filters from ReportingFilters
const selectedPathLvl2 = ref<number[]>([]);
const selectedPathLvl3 = ref<number[]>([]);
const selectedPathLvl4 = ref<number[]>([]);
const selectedCompletionStatus = ref<string | number>('');

function handleFiltersUpdate(payload: {
  path_lvl2: number[];
  path_lvl3: number[];
  path_lvl4: number[];
  completion_status: string | number;
}) {
  selectedPathLvl2.value = payload.path_lvl2;
  selectedPathLvl3.value = payload.path_lvl3;
  selectedPathLvl4.value = payload.path_lvl4;
  selectedCompletionStatus.value = payload.completion_status;
  fetchUnits();
}

const alert = ref(false);
const selectedUnitId = ref<string | number>('');

const units = computed(() => backofficeStore.units);
const loading = computed(() => backofficeStore.unitsLoading);
const reportingEmissionBreakdown = computed(
  () => units.value?.emission_breakdown ?? null,
);

function isFullyValidatedProgress(progress?: string): boolean {
  if (!progress) return false;
  const [validatedRaw, totalRaw] = progress.split('/');
  const validated = Number(validatedRaw);
  const total = Number(totalRaw);
  if (!Number.isFinite(validated) || !Number.isFinite(total)) return false;
  return total > 0 && validated >= total;
}

const tableRows = computed(() => units.value?.data ?? []);
const validatedCount = computed(
  () =>
    tableRows.value.filter((row) =>
      isFullyValidatedProgress(row.completion_progress),
    ).length,
);
const tableTotal = computed(() => tableRows.value.length);

async function fetchUnits() {
  if (selectedYears.value.length === 0) {
    backofficeStore.units = null;
    return;
  }
  const filtersToSend: {
    path_lvl2?: Array<number | string>;
    path_lvl3?: Array<number | string>;
    path_lvl4?: Array<number | string>;
    years?: string[];
    completion_status?: number | string;
    modules?: Array<{ module: string; state: ModuleState }>;
  } = {
    path_lvl2:
      selectedPathLvl2.value.length > 0 ? selectedPathLvl2.value : undefined,
    path_lvl3:
      selectedPathLvl3.value.length > 0 ? selectedPathLvl3.value : undefined,
    path_lvl4:
      selectedPathLvl4.value.length > 0 ? selectedPathLvl4.value : undefined,
    years: selectedYears.value,
    completion_status:
      selectedCompletionStatus.value !== ''
        ? selectedCompletionStatus.value
        : undefined,
    modules: Array.from(moduleStates.value.values()).map((data) => ({
      module: data.module,
      state: data.states.length > 0 ? data.states[0] : 0,
    })),
  };

  await backofficeStore.getUnits(filtersToSend);
}

onMounted(async () => {
  // Initialize all modules with all states selected by default
  const allStates = Object.values(MODULE_STATES);
  MODULE_CARDS.forEach((card) => {
    moduleStates.value.set(card.module, {
      module: card.module,
      states: [...allStates],
    });
  });

  await backofficeStore.getAvailableYears();
  await fetchUnits();
});

function handleViewUnit(unitId: string | number) {
  selectedUnitId.value = unitId;
  // alert.value = true;
  // WARNING, don't work if several selected YEARS
  router.push({
    name: 'results',
    params: { unit: unitId, year: selectedYears.value[0] },
  });
}

async function handleModuleStateUpdate(module: Module, states: ModuleState[]) {
  moduleStates.value.set(module, {
    module,
    states: [...states],
  });
  // Trigger reactivity by reassigning
  moduleStates.value = new Map(moduleStates.value);
  // Wait for computed property to update before fetching
  await nextTick();
  await fetchUnits();
}
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_REPORTING" />
    <div class="q-my-xl q-mx-lg">
      <div class="container full-width">
        <div class="q-mb-xs">
          <span class="text-h5 text-weight-medium">{{
            $t('backoffice_reporting_year_title')
          }}</span>
        </div>
        <span class="text-body2">{{
          $t('backoffice_reporting_year_description')
        }}</span>
        <ReportingYear
          @update:years="
            (y) => {
              selectedYears = y;
              fetchUnits();
            }
          "
        />
      </div>
      <div class="q-mt-xl">
        <ReportingFilters @update:filters="handleFiltersUpdate" />
      </div>
      <div class="q-mt-xl">
        <q-expansion-item
          icon="mdi-chart-arc"
          :label="
            $t('backoffice_reporting_module_status_label', {
              count: $t('backoffice_reporting_all_modules'),
            })
          "
        >
          <template #header>
            <div class="flex justify-between items-center" style="width: 100%">
              <span class="text-body1 text-weight-medium">{{
                $t('backoffice_reporting_module_status_label', {
                  count: $t('backoffice_reporting_all_modules'),
                })
              }}</span>
              <q-checkbox
                :model-value="allStatesSelected"
                :label="
                  allStatesSelected
                    ? $t('backoffice_reporting_unselect_all')
                    : $t('backoffice_reporting_select_all')
                "
                color="accent"
                size="sm"
                @update:model-value="(value) => toggleSelectAll(value)"
                @click.stop
              />
            </div>
          </template>
          <div class="q-pa-md">
            <div class="grid-3-col">
              <template
                v-for="moduleCard in MODULE_CARDS"
                :key="moduleCard.module"
              >
                <ModuleSelector
                  :module-card="moduleCard"
                  :model-value="
                    moduleStates.get(moduleCard.module)?.states || []
                  "
                  @update:model-value="
                    (states) =>
                      handleModuleStateUpdate(moduleCard.module, states)
                  "
                />
              </template>
            </div>
          </div>
        </q-expansion-item>
      </div>
      <div class="q-mt-xl">
        <UnitsTable
          :units="tableRows"
          :pagination="units?.pagination"
          :loading="loading"
          @view-unit="handleViewUnit"
        />
      </div>
      <!--  Usage Statistics Box #461 -->
      <ReportingStatCards
        v-if="(units?.data ?? []).length > 1"
        :stats="{
          [MODULE_STATES.Default]: 31,
          [MODULE_STATES.InProgress]: 1,
          [MODULE_STATES.Validated]: 13,
        }"
        :loading="false"
      />
      <ReportingStatCardUnit
        v-else
        :stats="{ total_entries: 12 }"
        :loading="false"
      />
      <!-- Aggregated Results Box #460 -->
      <div class="q-mt-xl">
        <CompletionRateBar
          :validated-units="validatedCount"
          :total-units="tableTotal"
          :scope-label="$t('backoffice_reporting_completion_bar_scope_table')"
        />
      </div>
      <q-card flat class="grid-2-col q-mt-xl">
        <ModuleCarbonFootprintChart
          :breakdown-data="reportingEmissionBreakdown"
          :title="$t('backoffice_reporting_aggregated_results_title')"
        />
        <CarbonFootPrintPerPersonChart
          :per-person-breakdown="
            reportingEmissionBreakdown?.per_person_breakdown ?? null
          "
          :validated-categories="
            reportingEmissionBreakdown?.validated_categories ?? null
          "
          :headcount-validated="
            reportingEmissionBreakdown?.validated_categories?.includes(
              'commuting',
            ) ?? false
          "
          :show-validation-placeholder="false"
          :title="$t('backoffice_reporting_aggregated_results_per_fte_title')"
        />
      </q-card>
      <EmissionBreakdownChart
        :breakdown-data="reportingEmissionBreakdown"
        class="q-mt-xl"
      />
      <div class="q-mt-xl">
        <div class="container full-width">
          <div class="q-mb-xs">
            <span class="text-h5 text-weight-medium">{{
              $t('backoffice_reporting_generate_report_title')
            }}</span>
          </div>
          <span class="text-body2">{{
            $t('backoffice_reporting_generate_report_description')
          }}</span>

          <ReportExport :units="[]" />
        </div>
      </div>
      <UnitDialogue v-model:model-value="alert" :unit-id="selectedUnitId" />
    </div>
  </q-page>
</template>
