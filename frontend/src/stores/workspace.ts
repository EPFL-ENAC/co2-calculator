import { defineStore } from 'pinia';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref, computed } from 'vue';
import { useAuthStore } from './auth';
import { api } from 'src/api/http';

interface Unit {
  id: number;
  name: string;
  principal_user_id: number;
  affiliations: string[];
  role?: string;
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
    const loading = ref(false);
    const unitsError = ref<Error | null>(null);
    const unitResultsError = ref<Error | null>(null);

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

    async function fetchUnits() {
      try {
        loading.value = true;
        unitsError.value = null;
        const user = useAuthStore().user;
        if (!user) {
          units.value = [];
          return;
        }

        const allUnits = (await (
          await fetch('/api/v1/units?limit=1', {
            credentials: 'include',
          })
        ).json()) as Unit[];

        units.value = allUnits;
      } catch (error) {
        console.error('Error fetching units:', error);
        unitsError.value =
          error instanceof Error ? error : new Error('Failed  to fetch units');
        units.value = [];
      } finally {
        loading.value = false;
      }
    }

    async function fetchUnit(id: number) {
      try {
        loading.value = true;
        const response = await fetch('/api/v1/units?limit=1', {
          credentials: 'include',
        });
        const allUnits = await response.json();
        selectedUnit.value = allUnits.find((u: Unit) => u.id === id) || null;
      } catch (error) {
        console.error('Error fetching unit:', error);
        selectedUnit.value = null;
      } finally {
        loading.value = false;
      }
    }

    async function fetchUnitResults(
      id: number,
      options?: {
        offset?: number;
        limit?: number;
        sort?: 'asc' | 'desc';
      },
    ) {
      try {
        loading.value = true;
        unitResultsError.value = null;
        console.log(
          'Fetching results for unit ID:',
          id,
          'with options:',
          options,
        );
        unitResults.value = (await (
          await fetch(`/api/v1/unit/${id}/results`, {
            credentials: 'include',
          })
        ).json()) as UnitResults;
      } catch (error) {
        console.error('Error fetching unit results:', error);
        unitResultsError.value =
          error instanceof Error
            ? error
            : new Error('Failed to fetch unit results');
        unitResults.value = null;
      } finally {
        loading.value = false;
      }
    }

    function reset() {
      selectedUnit.value = null;
      selectedYear.value = null;
      unitResults.value = null;
    }

    // Initialize from persisted state (Pinia plugin rehydrates state automatically).
    // We still preload results for the selected unit if available.
    async function initFromPersisted() {
      try {
        if (selectedUnit.value) {
          await fetchUnitResults(selectedUnit.value.id);
        }
      } catch {
        // ignore
      }
    }

    return {
      units,
      selectedUnit,
      selectedYear,
      unitResults,
      loading,
      unitsError,
      unitResultsError,
      availableYears,
      currentYearData,
      getLatestYear,
      fetchUnits,
      fetchUnit,
      fetchUnitResults,
      setUnit,
      setYear,
      reset,
      initFromPersisted,
    };
  },
  {
    persist: {
      key: 'workspace',
      paths: ['selectedUnit', 'selectedYear'],
      storage: localStorage,
    } as PersistenceOptions,
  },
);
