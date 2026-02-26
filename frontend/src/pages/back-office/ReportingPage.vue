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
import ReportingYear from 'src/components/organisms/backoffice/reporting/ReportingYear.vue';
import ReportingFilters from 'src/components/organisms/backoffice/reporting/ReportingFilters.vue';
import UnitsTable from 'src/components/organisms/backoffice/reporting/UnitsTable.vue';
import ReportExport from 'src/components/organisms/backoffice/reporting/ReportExport.vue';
import UnitDialogue from 'src/components/organisms/backoffice/reporting/UnitDialogue.vue';

const backofficeStore = useBackofficeStore();

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

function handleFiltersUpdate() {
  fetchUnits();
}

const alert = ref(false);
const selectedUnitId = ref<string | number>('');

const units = computed(() => backofficeStore.units);
const loading = computed(() => backofficeStore.unitsLoading);
// const affiliations = computed(() => backofficeStore.affiliations);
// const availableUnits = computed(() => backofficeStore.availableUnits);

async function fetchUnits() {
  // const filtersToSend: {
  //   affiliation?: string[];
  //   units?: number[];
  //   years?: string[];
  //   completion?: string;
  //   outlier_values?: boolean | null;
  //   modules?: Array<{ module: string; state: ModuleState }> | null;
  // } = {
  //   affiliation: filters.value.affiliation,
  //   units: filters.value.units,
  //   years: selectedYears.value,
  //   completion: filters.value.completion,
  //   outlier_values: filters.value.outlier_values,
  // };

  // // Check if any modules have states selected
  // const hasAnyStatesSelected = MODULE_CARDS.some((card) => {
  //   const data = moduleStates.value.get(card.module);
  //   return data && data.states.length > 0;
  // });

  // if (hasAnyStatesSelected) {
  //   // Some modules have states selected - send the filters
  //   filtersToSend.modules = moduleFilters.value.filters;
  // } else {
  //   // All modules are unselected - send empty array to return no results
  //   filtersToSend.modules = [];
  // }

  await backofficeStore.getUnits();
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

  // await backofficeStore.getAllUnits();
  await backofficeStore.getAvailableYears();
  await fetchUnits();
});

function handleViewUnit(unitId: string | number) {
  selectedUnitId.value = unitId;
  alert.value = true;
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
        <div class="flex justify-between items-center q-mb-sm">
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
          />
        </div>
        <div class="grid-3-col">
          <template v-for="moduleCard in MODULE_CARDS" :key="moduleCard.module">
            <ModuleSelector
              :module-card="moduleCard"
              :model-value="moduleStates.get(moduleCard.module)?.states || []"
              @update:model-value="
                (states) => handleModuleStateUpdate(moduleCard.module, states)
              "
            />
          </template>
        </div>
      </div>
      <div class="q-mt-xl">
        <UnitsTable
          :units="units?.data || []"
          :pagination="units?.pagination"
          :loading="loading"
          @view-unit="handleViewUnit"
        />
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
