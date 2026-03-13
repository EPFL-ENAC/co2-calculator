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

// Track selected units from ReportingFilters
const selectedUnits = ref<number[]>([]);

function handleFiltersUpdate(payload: {
  selectedUnits: number[];
  completion_status: string | number;
}) {
  selectedUnits.value = payload.selectedUnits;
  fetchUnits();
}

const alert = ref(false);
const selectedUnitId = ref<string | number>('');

const units = computed(() => backofficeStore.units);
const loading = computed(() => backofficeStore.unitsLoading);

async function fetchUnits() {
  const filtersToSend: {
    units?: number[];
    years?: string[];
    modules?: Array<{ module: string; state: ModuleState }>;
  } = {
    units: selectedUnits.value.length > 0 ? selectedUnits.value : undefined,
    years: selectedYears.value,
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
          :units="units?.data || []"
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
        <div class="container full-width">
          <!-- <div class="q-mb-xs">
            <span class="text-h5 text-weight-medium">{{
              $t('backoffice_reporting_aggregated_results_title')
            }}</span>
          </div>
          <span class="text-body2">{{
            $t('backoffice_reporting_aggregated_results_description')
          }}</span> -->

          <!-- Placeholder for aggregated results -->
          <div class="q-pa-md bg-grey-2 rounded">
            <img
              src="/placeholder-reporting.png"
              alt="Aggregated Results Placeholder"
              class="full-width"
            />
          </div>
        </div>
      </div>
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
