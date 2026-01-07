import { defineStore } from 'pinia';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref, computed } from 'vue';
import { api } from 'src/api/http';

export const WORKSPACE_DEFAULT_YEAR = 2025;

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
export interface Inventory {
  id: number;
  unit_id: string;
  year: number;
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

    // --- Inventory logic ---
    const inventories = ref<Inventory[]>([]); // backend inventory objects
    const inventoriesLoading = ref(false);
    const inventoriesError = ref<Error | null>(null);
    const selectedInventory = ref<Inventory | null>(null);

    // Fetch all inventories for a unit
    async function fetchInventoriesForUnit(unitId: string) {
      try {
        inventoriesLoading.value = true;
        inventoriesError.value = null;
        inventories.value = await api.get(`inventories/unit/${unitId}/`).json();
      } catch (error) {
        inventoriesError.value =
          error instanceof Error
            ? error
            : new Error('Failed to fetch inventories');
        inventories.value = [];
      } finally {
        inventoriesLoading.value = false;
      }
    }

    // Fetch inventory for a unit of a given year
    // /unit/{unit_id}/year/{year}/
    async function fetchInventoryForUnitYear(unitId: string, year: number) {
      try {
        inventoriesLoading.value = true;
        inventoriesError.value = null;
        const inv: Inventory | null = await api
          .get(`inventories/unit/${unitId}/year/${year}/`)
          .json();
        return inv;
      } catch (error) {
        inventoriesError.value =
          error instanceof Error
            ? error
            : new Error('Failed to fetch inventory for year');
        return null;
      } finally {
        inventoriesLoading.value = false;
      }
    }

    // Compute year range for selection (min year in DB or WORKSPACE_DEFAULT_YEAR, up to N-1)
    const availableInventoryYears = computed(() => {
      const currentYear = new Date().getFullYear();
      const yearsInDb = inventories.value.map((inv) => inv.year);
      // Find the minimum year in DB, but never less than WORKSPACE_DEFAULT_YEAR
      const minDbYear =
        yearsInDb.length > 0 ? Math.min(...yearsInDb) : WORKSPACE_DEFAULT_YEAR;
      // const minYear = Math.min(minDbYear, WORKSPACE_DEFAULT_YEAR); // unused
      const startYear =
        minDbYear < WORKSPACE_DEFAULT_YEAR ? minDbYear : WORKSPACE_DEFAULT_YEAR;
      const maxYear = currentYear - 1;
      const years: number[] = [];
      for (let y = startYear; y <= maxYear; y++) years.push(y);
      return years;
    });

    // Helper: does inventory exist for year?
    function inventoryForYear(year: number) {
      return inventories.value.find((inv) => inv.year === year) || null;
    }

    // Create inventory for a unit/year
    async function createInventory(
      unitId: string,
      year: number,
    ): Promise<Inventory> {
      try {
        inventoriesLoading.value = true;
        inventoriesError.value = null;
        const inv: Inventory = await api
          .post(`inventories/`, { json: { unit_id: unitId, year } })
          .json();
        inventories.value.push(inv);
        return inv;
      } catch (error) {
        inventoriesError.value =
          error instanceof Error
            ? error
            : new Error('Failed to create inventory');
        throw inventoriesError.value;
      } finally {
        inventoriesLoading.value = false;
      }
    }

    // Set selected inventory by year (create if needed)
    async function selectInventoryForYear(unitId: string, year: number) {
      let inv: Inventory | null = await fetchInventoryForUnitYear(unitId, year);
      if (!inv) {
        inv = await createInventory(unitId, year);
      }
      selectedInventory.value = inv;
      return inv;
    }

    // Set selected inventory by year (create if needed)
    async function selectWithoutFetchingInventoryForYear(
      unitId: string,
      year: number,
    ) {
      let inv = await inventoryForYear(year);
      if (!inv) {
        inv = await createInventory(unitId, year);
      }
      selectedInventory.value = inv;
      return inv;
    }

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
      // Inventory logic
      inventories,
      inventoriesLoading,
      inventoriesError,
      selectedInventory,
      fetchInventoriesForUnit,
      availableInventoryYears,
      inventoryForYear,
      createInventory,
      selectInventoryForYear,
      selectWithoutFetchingInventoryForYear,
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
