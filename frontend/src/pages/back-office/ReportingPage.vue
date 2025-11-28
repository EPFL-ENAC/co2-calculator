<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import { MODULES } from 'src/constant/modules';
import { ModuleState } from 'src/constant/moduleStates';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import type { Module } from 'src/constant/modules';
import { api } from 'src/api/http';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import ModuleSelector, {
  type ModuleStateData,
} from 'src/components/organisms/backoffice/reporting/ModuleSelector.vue';
import ReportingYear from 'src/components/organisms/backoffice/reporting/ReportingYear.vue';
import ReportingFilters from 'src/components/organisms/backoffice/reporting/ReportingFilters.vue';
import UnitsTable from 'src/components/organisms/backoffice/reporting/UnitsTable.vue';
import ReportExport from 'src/components/organisms/backoffice/reporting/ReportExport.vue';
import UnitDialogue from 'src/components/organisms/backoffice/reporting/UnitDialogue.vue';

const moduleStates = ref<Map<Module, ModuleStateData>>(new Map());
const enabledModulesSet = ref<Set<Module>>(new Set());

const enabledModules = computed(() =>
  Array.from(enabledModulesSet.value)
    .map((module) => moduleStates.value.get(module))
    .filter((state): state is ModuleStateData => state !== undefined),
);

const moduleFilters = computed(() => {
  const filters: Array<{ module: string; state: string }> = [];
  const enabledModulesWithNoStates: string[] = [];

  moduleStates.value.forEach((data, module) => {
    if (enabledModulesSet.value.has(module)) {
      // Map frontend module name to backend module name
      const backendModuleName = getBackendModuleName(module);

      if (data.states.length > 0) {
        // Module has states selected - add them to filters
        data.states.forEach((state) => {
          filters.push({ module: backendModuleName, state });
        });
      } else {
        // Module is enabled but has no states selected - mark for empty result
        enabledModulesWithNoStates.push(backendModuleName);
      }
    }
  });

  return { filters, hasEmptyModule: enabledModulesWithNoStates.length > 0 };
});

// Helper function to map frontend module name to backend module name
function getBackendModuleName(frontendModule: Module): string {
  const moduleMap: Record<Module, string> = {
    [MODULES.MyLab]: 'my_lab',
    [MODULES.ProfessionalTravel]: 'professional_travel',
    [MODULES.Infrastructure]: 'infrastructure',
    [MODULES.EquipmentElectricConsumption]: 'equipment_electric_consumption',
    [MODULES.Purchase]: 'purchase',
    [MODULES.InternalServices]: 'internal_services',
    [MODULES.ExternalCloud]: 'external_cloud',
  };
  return moduleMap[frontendModule] || frontendModule;
}

const selectedYears = ref<string[]>(['2026']); // Default to latest year

const filters = ref({
  affiliation: [] as string[],
  units: [] as string[],
  completion: '',
  outlier_values: null as boolean | null,
  search: '',
});

function handleFiltersUpdate(newFilters: {
  affiliation: string[];
  units: string[];
  completion: string;
  outlier_values: boolean | null;
  search: string;
}) {
  filters.value = newFilters;
  fetchUnits();
}

const alert = ref(false);
const selectedUnitId = ref<string | number>('');

interface ModuleCompletion {
  status: ModuleState;
  outlier_values: number;
}

interface BackofficeUnitData {
  id: string | number;
  completion: Record<string, ModuleCompletion>;
  completion_counts: {
    validated: number;
    in_progress: number;
    default: number;
  };
  unit: string;
  affiliation: string;
  principal_user: string;
  last_update: string;
  outlier_values: number;
  expected_total?: number;
}

const units = ref<BackofficeUnitData[]>([]);
const allUnits = ref<BackofficeUnitData[]>([]);
const loading = ref(false);

async function fetchUnits(updateAllUnits = false) {
  if (updateAllUnits) {
    try {
      const data = await api
        .get('backoffice/units')
        .json<BackofficeUnitData[]>();
      allUnits.value = data;
    } catch (error) {
      console.error('Failed to fetch all units:', error);
    }
    return;
  }

  // Fetch filtered units
  loading.value = true;
  try {
    const searchParams = new URLSearchParams();

    // Add array filters (affiliation, units, years)
    const arrayFilters = [
      { key: 'affiliation', value: filters.value.affiliation },
      { key: 'units', value: filters.value.units },
      { key: 'years', value: selectedYears.value },
    ];

    arrayFilters.forEach(({ key, value }) => {
      if (Array.isArray(value) && value.length > 0) {
        value.forEach((v) => searchParams.append(key, String(v)));
      }
    });

    // Add string filters (completion, search)
    const completion = filters.value.completion?.trim();
    if (completion) {
      searchParams.append('completion', completion);
    }

    const search = filters.value.search?.trim();
    if (search) {
      searchParams.append('search', search);
    }

    // Add boolean filter (outlier_values)
    if (filters.value.outlier_values !== null) {
      searchParams.append(
        'outlier_values',
        String(filters.value.outlier_values),
      );
    }

    // Add module filters
    if (moduleFilters.value.hasEmptyModule) {
      searchParams.append('modules', '');
    } else {
      moduleFilters.value.filters.forEach((f) => {
        searchParams.append('modules', `${f.module}:${f.state}`);
      });
    }

    const queryString = searchParams.toString();
    const url = queryString
      ? `backoffice/units?${queryString}`
      : 'backoffice/units';

    console.log('Fetching units with url:', url);
    const data = await api.get(url).json<BackofficeUnitData[]>();
    console.log('Received units:', data);
    units.value = data;
  } catch (error) {
    console.error('Failed to fetch units:', error);
    units.value = [];
  } finally {
    loading.value = false;
  }
}

const affiliations = computed(() => {
  const uniqueAffiliations = new Set<string>();
  allUnits.value.forEach((unit) => {
    if (unit.affiliation) {
      uniqueAffiliations.add(unit.affiliation);
    }
  });
  return Array.from(uniqueAffiliations).sort();
});

const availableUnits = computed(() => {
  const uniqueUnits = new Set<string>();
  allUnits.value.forEach((unit) => {
    if (unit.unit) {
      uniqueUnits.add(unit.unit);
    }
  });
  return Array.from(uniqueUnits).sort();
});

onMounted(async () => {
  await fetchUnits(true);
  // Initial fetch without filters to get all units
  await fetchUnits();
});

function handleViewUnit(unitId: string | number) {
  selectedUnitId.value = unitId;
  alert.value = true;
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
        <ReportingFilters
          :affiliations="affiliations"
          :units="availableUnits"
          @update:filters="handleFiltersUpdate"
        />
      </div>
      <div class="q-mt-xl">
        <div class="flex justify-between q-mb-sm">
          <span class="text-body1 text-weight-medium">{{
            $t('backoffice_reporting_module_status_label', {
              count:
                enabledModules.length === 0 ||
                enabledModules.length === MODULE_CARDS.length
                  ? $t('backoffice_reporting_all_modules')
                  : enabledModules.length,
            })
          }}</span>
        </div>
        <div class="grid-3-col">
          <template v-for="moduleCard in MODULE_CARDS" :key="moduleCard.module">
            <ModuleSelector
              :module-card="moduleCard"
              @update="
                (data) => {
                  moduleStates.set(data.module, data);
                  fetchUnits();
                }
              "
              @enabled-change="
                (module, enabled) => {
                  if (enabled) {
                    enabledModulesSet.add(module);
                  } else {
                    enabledModulesSet.delete(module);
                  }
                  fetchUnits();
                }
              "
            />
          </template>
        </div>
      </div>
      <div class="q-mt-xl">
        <UnitsTable
          :units="units"
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

          <ReportExport :units="units" />
        </div>
      </div>
      <UnitDialogue v-model:model-value="alert" :unit-id="selectedUnitId" />
    </div>
  </q-page>
</template>
