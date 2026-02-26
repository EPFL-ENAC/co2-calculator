import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from 'src/api/http';
import type { ModuleState } from 'src/constant/moduleStates';

// interface ModuleCompletion {
//   status: ModuleState;
//   outlier_values: number;
// }

// "id": 1574,
// "unit_name": "Abbott, Guerrero and Rhodes",
// "affiliation": "SV",
// "validation_status": "3/9",
// "principal_user": "Melissa Paul",
// "last_update": "2026-02-20T15:19:37.859926",
// "highest_result_category": "Module infrastructure",
// "total_carbon_footprint": 231.91,
// "view_url": "/backoffice/unit/1574"

interface BackofficeUnitData {
  id: string | number;
  unit_name: string;
  affiliation: string;
  validation_status: string;
  principal_user: string;
  last_update: string;
  highest_result_category: string;
  total_carbon_footprint: number;
  view_url: string;
}

interface BackofficeUnitDataPagination {
  data: BackofficeUnitData[];
  pagination: {
    page: number;
    page_size: number;
    total_pages: number;
    total: number;
  };
}

interface UnitFilters {
  affiliation?: string[];
  units?: number[];
  years?: string[];
  completion?: string;
  outlier_values?: boolean | null;
  search?: string;
  modules?: Array<{ module: string; state: ModuleState }>;
}

export const useBackofficeStore = defineStore('backoffice', () => {
  // should be paginated already!
  const units = ref<BackofficeUnitDataPagination | null>(null);

  const allUnits = ref<BackofficeUnitData[]>([]);
  const selectedUnit = ref<BackofficeUnitData | null>(null);
  const unitsLoading = ref(false);
  const allUnitsLoading = ref(false);
  const unitLoading = ref(false);
  const unitsErrors = ref<Error[]>([]);
  const allUnitsErrors = ref<Error[]>([]);
  const unitErrors = ref<Error[]>([]);
  const availableYearsList = ref<string[]>([]);
  const latestYear = ref<string>('');
  const yearsLoading = ref(false);
  const yearsErrors = ref<Error[]>([]);

  // const affiliations = computed(() => {
  //   const uniqueAffiliations = new Set<string>();
  //   allUnits.value.forEach((unit) => {
  //     if (unit.affiliation) {
  //       uniqueAffiliations.add(unit.affiliation);
  //     }
  //   });
  //   return Array.from(uniqueAffiliations).sort();
  // });

  // const availableUnits = computed(() => {
  //   const uniqueUnits = new Set<number>();
  //   allUnits.value.forEach((unit) => {
  //     if (unit.unit) {
  //       uniqueUnits.add(unit.unit);
  //     }
  //   });
  //   return Array.from(uniqueUnits).sort();
  // });

  // async function getAllUnits() {
  //   try {
  //     allUnitsLoading.value = true;
  //     allUnitsErrors.value = [];
  //     const data = await api
  //       .get('backoffice/units')
  //       .json<BackofficeUnitData[]>();
  //     allUnits.value = data || [];
  //   } catch (error) {
  //     console.error('Error getting all units:', error);
  //     const errorObj =
  //       error instanceof Error ? error : new Error('Failed to get all units');
  //     allUnitsErrors.value = [errorObj];
  //     allUnits.value = [];
  //   } finally {
  //     allUnitsLoading.value = false;
  //   }
  // }

  async function getUnits(filters?: UnitFilters) {
    try {
      unitsLoading.value = true;
      unitsErrors.value = [];

      const searchParams = new URLSearchParams();

      // Add array filters (affiliation, units, years)
      if (filters?.affiliation && filters.affiliation.length > 0) {
        filters.affiliation.forEach((v) =>
          searchParams.append('affiliation', String(v)),
        );
      }

      if (filters?.units && filters.units.length > 0) {
        filters.units.forEach((v) => searchParams.append('units', String(v)));
      }

      if (filters?.years && filters.years.length > 0) {
        filters.years.forEach((v) => searchParams.append('years', String(v)));
      }

      // Add string filters (completion, search)
      if (filters?.completion?.trim()) {
        searchParams.append('completion', filters.completion.trim());
      }

      if (filters?.search?.trim()) {
        searchParams.append('search', filters.search.trim());
      }

      // Add boolean filter (outlier_values)
      if (
        filters?.outlier_values !== null &&
        filters?.outlier_values !== undefined
      ) {
        searchParams.append('outlier_values', String(filters.outlier_values));
      }

      // Add module filters
      if (filters?.modules !== undefined) {
        if (filters.modules.length === 0) {
          // Empty array means modules are enabled but no states selected
          // Send empty string to backend - it will return empty results
          searchParams.append('modules', '');
        } else {
          // Send module filters
          filters.modules.forEach((f) => {
            searchParams.append('modules', `${f.module}:${f.state}`);
          });
        }
      }

      const queryString = searchParams.toString();
      const url = queryString
        ? `backoffice/units?${queryString}`
        : 'backoffice/units';

      const data = await api.get(url).json<BackofficeUnitDataPagination>();
      units.value = data || [];
    } catch (error) {
      console.error('Error getting units:', error);
      const errorObj =
        error instanceof Error ? error : new Error('Failed to get units');
      unitsErrors.value = [errorObj];
      units.value = null;
    } finally {
      unitsLoading.value = false;
    }
  }

  async function getUnit(id: string | number) {
    try {
      unitLoading.value = true;
      unitErrors.value = [];
      const data = await api
        .get(`backoffice/unit/${id}`)
        .json<BackofficeUnitData>();
      selectedUnit.value = data;
      return data;
    } catch (error) {
      console.error('Error getting unit:', error);
      const errorObj =
        error instanceof Error ? error : new Error('Failed to get unit');
      unitErrors.value = [errorObj];
      selectedUnit.value = null;
      return null;
    } finally {
      unitLoading.value = false;
    }
  }

  function setSelectedUnit(unit: BackofficeUnitData | null) {
    selectedUnit.value = unit;
  }

  async function getAvailableYears() {
    try {
      yearsLoading.value = true;
      yearsErrors.value = [];
      const data = await api
        .get('backoffice/years')
        .json<{ years: string[]; latest: string }>();
      availableYearsList.value = data.years || [];
      latestYear.value = data.latest || '';
      return { years: data.years, latest: data.latest };
    } catch (error) {
      console.error('Error getting available years:', error);
      const errorObj =
        error instanceof Error
          ? error
          : new Error('Failed to get available years');
      yearsErrors.value = [errorObj];
      availableYearsList.value = [];
      latestYear.value = '';
      return { years: [], latest: '' };
    } finally {
      yearsLoading.value = false;
    }
  }

  function reset() {
    selectedUnit.value = null;
  }

  return {
    units,
    allUnits,
    selectedUnit,
    unitsLoading,
    allUnitsLoading,
    unitLoading,
    unitsErrors,
    allUnitsErrors,
    unitErrors,
    availableYearsList,
    latestYear,
    yearsLoading,
    yearsErrors,
    // affiliations,
    // availableUnits,
    // getAllUnits,
    getUnits,
    getUnit,
    getAvailableYears,
    setSelectedUnit,
    reset,
  };
});
