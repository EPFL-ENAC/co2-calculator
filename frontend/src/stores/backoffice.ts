import { defineStore } from 'pinia';
import { reactive, ref } from 'vue';
import { api } from 'src/api/http';
import type { ModuleState } from 'src/constant/moduleStates';
import type { EmissionBreakdownResponse } from 'src/stores/modules';

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE_UNITS = 10;

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
  total_fte?: number | null;
  view_url: string;
  completion?: number;
  completion_progress?: string;
}

interface BackofficeUnitDataPagination {
  data: BackofficeUnitData[];
  pagination: {
    page: number;
    page_size: number;
    total_pages: number;
    total: number;
  };
  emission_breakdown?: EmissionBreakdownResponse | null;
  validated_units_count?: number;
  in_progress_units_count?: number;
  not_started_units_count?: number;
  total_units_count?: number;
  module_status_counts?: Record<number, number> | null;
}

export interface UnitFilters {
  path_affiliation?: Array<number | string>;
  path_lvl4?: Array<number | string>;
  years?: string[];
  completion_status?: number | string;
  outlier_values?: boolean | null;
  search?: string;
  modules?: Array<{ module: string; state: ModuleState }>;
}

export interface PaginationState {
  page: number;
  pageSize: number;
  sortBy?: string;
  descending?: boolean;
}

export const useBackofficeStore = defineStore('backoffice', () => {
  const units = ref<BackofficeUnitDataPagination | null>(null);
  const unit = ref<BackofficeUnitData | null>(null);

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

  const unitsPagination = reactive<PaginationState>({
    page: DEFAULT_PAGE,
    pageSize: DEFAULT_PAGE_SIZE_UNITS,
    sortBy: undefined,
    descending: false,
  });

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
    console.log(
      '📡 [BackofficeStore] getUnits called with pagination:',
      JSON.stringify(unitsPagination, null, 2),
    );

    try {
      unitsLoading.value = true;
      unitsErrors.value = [];

      const searchParams = new URLSearchParams();
      searchParams.append('page', String(unitsPagination.page));
      // Send 0 for "all" (no pagination), otherwise send actual page size
      const apiPageSize =
        unitsPagination.pageSize >= 5000 ? 0 : unitsPagination.pageSize;
      searchParams.append('page_size', String(apiPageSize));

      // Send sort parameters if sortBy is set
      if (unitsPagination.sortBy) {
        searchParams.append('sort_by', unitsPagination.sortBy);
        searchParams.append(
          'sort_order',
          unitsPagination.descending ? 'desc' : 'asc',
        );
        console.log('🔀 [BackofficeStore] Sort params:', {
          sort_by: unitsPagination.sortBy,
          sort_order: unitsPagination.descending ? 'desc' : 'asc',
        });
      }

      // Add hierarchy filters
      if (filters?.path_affiliation && filters.path_affiliation.length > 0) {
        filters.path_affiliation.forEach((v) =>
          searchParams.append('path_affiliation', String(v)),
        );
      }

      if (filters?.path_lvl4 && filters.path_lvl4.length > 0) {
        filters.path_lvl4.forEach((v) =>
          searchParams.append('path_lvl4', String(v)),
        );
      }

      if (filters?.years && filters.years.length > 0) {
        filters.years.forEach((v) => searchParams.append('years', String(v)));
      }

      // Add status/search filters
      if (
        filters?.completion_status !== undefined &&
        filters?.completion_status !== ''
      ) {
        searchParams.append(
          'completion_status',
          String(filters.completion_status),
        );
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
      units.value = data || null;
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
      unit.value = data;
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
    unitsPagination,
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
