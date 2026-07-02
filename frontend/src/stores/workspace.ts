import { defineStore } from 'pinia';
import { HTTPError } from 'ky';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref, computed } from 'vue';
import { api } from 'src/api/http';

export interface Unit {
  id: number;
  name: string;
  institutional_id: string;
  principal_user_id: string;
  principal_user_function: string;
  principal_user_name: string;
  principal_user_email?: string | null;
  affiliations: string[];
  current_user_role: string;
  visibility?: string;
}

/** Build the `id-slugified-name` unit route param used by the workspace routes. */
export function unitSlug(unit: Unit): string {
  return `${unit.id}-${unit.name.replace(/\s+/g, '-').toLowerCase()}`;
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

interface SelectedParams {
  year: number;
  unit: string; // unit id-name string
}
export interface CarbonReportStats {
  // Pre-computed aggregate written by the backend. `total` is in kg CO2eq.
  total?: number | null;
  [key: string]: unknown;
}
export interface CarbonReport {
  id: number;
  unit_id: number;
  year: number;
  reference_year?: number | null;
  carbon_project_id: number;
  stats?: CarbonReportStats | null;
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

    // --- CarbonReport logic ---
    const carbonReports = ref<CarbonReport[]>([]); // backend carbon reports objects
    const carbonReportsLoading = ref(false);
    const carbonReportsError = ref<Error | null>(null);
    const selectedCarbonReport = ref<CarbonReport | null>(null);
    // Fetch all carbon reports for a unit
    async function fetchCarbonReportsForUnit(unitId: number) {
      try {
        carbonReportsLoading.value = true;
        carbonReportsError.value = null;
        carbonReports.value = await api
          .get(`carbon-reports/unit/${unitId}/`)
          .json();
      } catch (error) {
        carbonReportsError.value =
          error instanceof Error
            ? error
            : new Error('Failed to fetch carbon reports for unit');
        carbonReports.value = [];
      } finally {
        carbonReportsLoading.value = false;
      }
    }

    // Fetch carbon report for a unit of a given year
    // /unit/{unit_id}/year/{year}/
    async function fetchCarbonReportForUnitYear(unitId: number, year: number) {
      try {
        carbonReportsLoading.value = true;
        carbonReportsError.value = null;
        const inv: CarbonReport | null = await api
          .get(`carbon-reports/unit/${unitId}/year/${year}/`)
          .json();
        return inv;
      } catch (error) {
        carbonReportsError.value =
          error instanceof Error
            ? error
            : new Error('Failed to fetch carbon report for year');
        return null;
      } finally {
        carbonReportsLoading.value = false;
      }
    }

    // Helper: does carbon report exist for year?
    function carbonReportForYear(year: number) {
      return carbonReports.value.find((inv) => inv.year === year) || null;
    }

    // Create carbon report for a unit/year
    async function createCarbonReport(
      unitId: number,
      year: number,
    ): Promise<CarbonReport> {
      try {
        carbonReportsLoading.value = true;
        carbonReportsError.value = null;
        const inv: CarbonReport = await api
          .post(`carbon-reports/`, { json: { unit_id: unitId, year } })
          .json();
        carbonReports.value.push(inv);
        return inv;
      } catch (error) {
        carbonReportsError.value =
          error instanceof Error
            ? error
            : new Error('Failed to create carbon report');
        throw carbonReportsError.value;
      } finally {
        carbonReportsLoading.value = false;
      }
    }

    // Set selected carbon report by year (create if needed)
    async function selectCarbonReportForYear(unitId: number, year: number) {
      let inv: CarbonReport | null = await fetchCarbonReportForUnitYear(
        unitId,
        year,
      );
      if (!inv) {
        inv = await createCarbonReport(unitId, year);
      }
      selectedCarbonReport.value = inv;
      return inv;
    }

    async function selectSimulatorExploreCarbonReport(
      unitId: number,
      referenceYear: number,
    ) {
      const url = `carbon-reports/simulator/explore/unit/${unitId}/reference-year/${referenceYear}/`;
      let inv: CarbonReport;
      try {
        // 404 is expected here — the catch branch seeds an explore report.
        // Opt out of the global error toast for that status only.
        inv = await api.get(url, { skipErrorCodes: [404] }).json();
      } catch (err) {
        if (err instanceof HTTPError && err.response.status === 404) {
          // No explore report exists yet — seed one from the Calculator report.
          inv = await api.post(url).json();
        } else {
          throw err;
        }
      }
      selectedCarbonReport.value = inv;
      return inv;
    }

    // Set selected carbon report by year (create if needed)
    async function selectWithoutFetchingCarbonReportForYear(
      unitId: number,
      year: number,
    ) {
      let inv = await carbonReportForYear(year);
      if (!inv) {
        inv = await createCarbonReport(unitId, year);
      }
      selectedCarbonReport.value = inv;
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
      // CarbonReport logic
      carbonReports,
      carbonReportsLoading,
      carbonReportsError,
      selectedCarbonReport,
      fetchCarbonReportsForUnit,
      carbonReportForYear,
      createCarbonReport,
      selectCarbonReportForYear,
      selectWithoutFetchingCarbonReportForYear,
      selectSimulatorExploreCarbonReport,
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
