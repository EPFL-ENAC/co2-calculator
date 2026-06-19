import { defineStore } from 'pinia';
import { reactive, ref } from 'vue';
import { api } from 'src/api/http';
import { applyUnitFiltersToParams } from 'src/api/backoffice';
import type { ModuleState } from 'src/constant/moduleStates';
import type {
  EmissionBreakdownResponse,
  ItBreakdownResponse,
} from 'src/stores/modules';

const DEFAULT_PAGE = 1;
const DEFAULT_PAGE_SIZE_UNITS = 10;

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
  it_breakdown?: ItBreakdownResponse | null;
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
  overall_status?: number | string;
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

      if (filters) {
        applyUnitFiltersToParams(searchParams, filters);
        // Empty modules array means filter is active but nothing selected → no results
        if (filters.modules !== undefined && filters.modules.length === 0) {
          searchParams.append('modules', '');
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
