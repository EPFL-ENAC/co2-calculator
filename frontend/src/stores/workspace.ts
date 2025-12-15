import { defineStore } from 'pinia';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref, computed } from 'vue';
import { api } from 'src/api/http';

export interface Unit {
  id: number;
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
  id: number;
  name: string;
  updated_at: number;
  years: YearResult[];
}

export const useWorkspaceStore = defineStore(
  'workspace',
  () => {
    const units = ref<Unit[]>([]);
    const selectedUnit = ref<Unit | null>(null);
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

    const availableYears = computed(() => {
      return unitResults.value?.years.map((y) => y.year) || [];
    });

    const currentYearData = computed(() => {
      if (!unitResults.value || !selectedYear.value) return null;
      return unitResults.value.years.find((y) => y.year === selectedYear.value);
    });

    function getLatestYear(unitId: number): number | null {
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

    async function getUnit(id: number) {
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
      id: number,
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
    }

    return {
      units,
      selectedUnit,
      selectedYear,
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
      reset,
    };
  },
  {
    persist: {
      key: 'workspaceLocalStorage',
      pick: ['selectedUnit', 'selectedYear'],
      storage: localStorage,
    } as PersistenceOptions,
  },
);
