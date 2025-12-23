import { defineStore } from 'pinia';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref, computed } from 'vue';
import { api } from 'src/api/http';

export interface Unit {
  id: string;
  name: string;
  principal_user_id: string;
  principal_user_function: string;
  principal_user_name: string;
  affiliations: string[];
  current_user_role: string;
  visibility?: string;
}
interface YearResult {
  year: number;
  completed_modules: number;
  kgco2: number;
  last_year_comparison?: number;
  report: string;
}

interface UnitResults {
  id: string;
  name: string;
  updated_at: number;
  years: YearResult[];
}

interface SelectedParams {
  year: number;
  unit: string; // unit id-name string
}

export const useWorkspaceStore = defineStore(
  'workspace',
  () => {
    const units = ref<Unit[]>([]);
    const selectedUnit = ref<Unit | null>(null);
    const selectedParams = ref<SelectedParams | null>(null);
    const selectedYear = ref<number | null>(null);
    const unitResults = ref<UnitResults | null>(null);
    const unitsLoading = ref(false);
    const unitLoading = ref(false);
    const unitResultsLoading = ref(false);
    const unitsErrors = ref<Error[]>([]);
    const unitErrors = ref<Error[]>([]);
    const unitResultsErrors = ref<Error[]>([]);

    function setUnit(unit: Unit) {
      selectedUnit.value = unit;
    }

    function setYear(year: number) {
      selectedYear.value = year;
    }

    function setSelectedParams(params: SelectedParams) {
      selectedParams.value = params;
    }
    const availableYears = computed(() => {
      return unitResults.value?.years.map((y) => y.year) || [];
    });

    const currentYearData = computed(() => {
      if (!unitResults.value || !selectedYear.value) return null;
      return unitResults.value.years.find((y) => y.year === selectedYear.value);
    });

    function getLatestYear(unitId: string): number | null {
      if (
        !unitResults.value ||
        unitResults.value.id !== unitId ||
        !unitResults.value.years.length
      ) {
        return null;
      }
      return Math.max(...unitResults.value.years.map((y) => y.year));
    }

    async function getUnits() {
      try {
        unitsLoading.value = true;
        unitsErrors.value = [];

        const allUnits = (await api.get('users/units').json()) as Unit[];

        units.value = allUnits || [];
      } catch (error) {
        console.error('Error getting units:', error);
        const errorObj =
          error instanceof Error ? error : new Error('Failed to get units');
        unitsErrors.value = [errorObj];
        units.value = [];
      } finally {
        unitsLoading.value = false;
      }
    }

    async function getUnit(id: string) {
      try {
        unitLoading.value = true;
        unitErrors.value = [];
        selectedUnit.value = (await api.get(`units/${id}`).json()) as Unit;
      } catch (error) {
        console.error('Error getting unit:', error);
        const errorObj =
          error instanceof Error ? error : new Error('Failed to get unit');
        unitErrors.value = [errorObj];
        selectedUnit.value = null;
      } finally {
        unitLoading.value = false;
      }
    }

    async function getUnitResults(
      id: string,
      options?: {
        offset?: number;
        limit?: number;
        sort?: 'asc' | 'desc';
      },
    ) {
      try {
        unitResultsLoading.value = true;
        unitResultsErrors.value = [];

        unitResults.value = (await api
          .get(`unit/${id}/results`, { searchParams: options })
          .json()) as UnitResults;
      } catch (error) {
        console.error('Error getting unit results:', error);
        const errorObj =
          error instanceof Error
            ? error
            : new Error('Failed to get unit results');
        unitResultsErrors.value = [errorObj];
        unitResults.value = null;
      } finally {
        unitResultsLoading.value = false;
      }
    }

    function reset() {
      selectedUnit.value = null;
      selectedYear.value = null;
      unitResults.value = null;
      selectedParams.value = null;
    }

    return {
      units,
      selectedUnit,
      selectedYear,
      selectedParams,
      unitResults,
      unitsLoading,
      unitLoading,
      unitResultsLoading,
      unitsErrors,
      unitErrors,
      unitResultsErrors,
      availableYears,
      currentYearData,
      getLatestYear,
      getUnits,
      getUnit,
      getUnitResults,
      setUnit,
      setYear,
      setSelectedParams,
      reset,
    };
  },
  {
    persist: {
      key: 'workspaceLocalStorage',
      pick: ['selectedParams'],
      storage: localStorage,
    } as PersistenceOptions,
  },
);
