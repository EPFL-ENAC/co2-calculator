import { defineStore } from 'pinia';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref, computed } from 'vue';

interface Unit {
  id: number;
  name: string;
  principal_user_id: number;
  affiliations: string[];
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

    async function fetchUnits() {
      try {
        loading.value = true;
        // TODO: Replace with real API when available
        // units.value = await api.get('units/all').json<Unit[]>();
        const response = await fetch('/mock/units.json');
        units.value = await response.json();
      } catch (error) {
        console.error('Error fetching units:', error);
        units.value = [];
      } finally {
        loading.value = false;
      }
    }

    async function fetchUnit(id: number) {
      try {
        loading.value = true;
        // TODO: Replace with real API when available
        // const unit = await api.get(`units/${id}`).json<Unit>();
        const response = await fetch('/mock/units.json');
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
        console.log(
          'Fetching results for unit ID:',
          id,
          'with options:',
          options,
        );
        // TODO: Replace with real API when available
        // const params = new URLSearchParams();
        // if (options?.offset) params.append('offset', String(options.offset));
        // if (options?.limit) params.append('limit', String(options.limit));
        // if (options?.sort) params.append('sort', options.sort);
        // unitResults.value = await api.get(`units/${id}/results?${params}`).json<UnitResults>();

        const response = await fetch('/mock/unit-results.json');
        unitResults.value = await response.json();
      } catch (error) {
        console.error('Error fetching unit results:', error);
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
      availableYears,
      currentYearData,
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
      storage: sessionStorage,
    } as PersistenceOptions,
  },
);
