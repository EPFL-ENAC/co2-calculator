import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { Cookies } from 'quasar';

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

export const useWorkspaceStore = defineStore('workspace', () => {
  const units = ref<Unit[]>([]);
  const selectedUnit = ref<Unit | null>(null);
  const selectedYear = ref<number | null>(null);
  const unitResults = ref<UnitResults | null>(null);
  const loading = ref(false);

  // Cookie helpers using Quasar
  function setCookie(name: string, value: string, days = 30) {
    Cookies.set(name, value, { expires: days });
  }

  function getCookie(name: string): string | null {
    return Cookies.get(name) || null;
  }

  function deleteCookie(name: string) {
    Cookies.remove(name);
  }

  function setUnit(unit: Unit) {
    selectedUnit.value = unit;
    // Persist only unit name in cookies
    setCookie('workspace_unit_name', unit.name);
  }

  function setYear(year: number) {
    selectedYear.value = year;
    // Persist year in cookies
    setCookie('workspace_year', String(year));
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
    // Clear cookies
    deleteCookie('workspace_unit_name');
    deleteCookie('workspace_year');
  }

  async function initFromCookies() {
    try {
      const unitName = getCookie('workspace_unit_name');
      const yearStr = getCookie('workspace_year');

      if (unitName) {
        // Ensure units are loaded
        if (units.value.length === 0) {
          await fetchUnits();
        }
        const unit = units.value.find((u) => u.name === unitName) || null;
        if (unit) {
          selectedUnit.value = unit;
          // Preload results for this unit
          try {
            await fetchUnitResults(unit.id);
          } catch {
            // no-op
          }
        }
      }
      if (yearStr) {
        const y = Number(yearStr);
        if (!Number.isNaN(y)) {
          selectedYear.value = y;
        }
      }
    } catch {
      // If cookies are malformed, clear them
      deleteCookie('workspace_unit_name');
      deleteCookie('workspace_year');
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
    initFromCookies,
  };
});
