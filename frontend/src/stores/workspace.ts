import { defineStore } from 'pinia';
import { HTTPError } from 'ky';
import type { PersistenceOptions } from 'pinia-plugin-persistedstate';
import { ref, computed } from 'vue';
import { api } from 'src/api/http';
import type { SimulatorPlan } from 'src/stores/simulatorPlans';

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
  // Optional: nothing in the frontend reads it, and the slim workspace-home
  // payload no longer ships it (only full CarbonReport fetches do).
  carbon_project_id?: number;
  stats?: CarbonReportStats | null;
}

/**
 * Minimal aggregate payload from `GET /workspace/{unit}/{year}/home`. Collapses
 * the workspace/stats dependency chain into one response; the workspace guard
 * distributes each field into the relevant store. Loosely typed here to avoid
 * coupling the workspace store to the modules/yearConfig store internals — the
 * guard casts as it hydrates.
 */
export interface WorkspaceHomePayload {
  carbon_report_id: number;
  year_config: unknown | null;
  /** Persisted report stats (buckets shape) with the validated headline merged. */
  stats: Record<string, unknown>;
  /** Per-module status map, fanned out to the timeline store by the guard. */
  module_states: { module_type_id: number; status: number }[];
  /** The unit's visible Simulator Plans with their totals, for the home table. */
  project_plans: SimulatorPlan[];
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
    const carbonReportsLoading = ref(false);
    const carbonReportsError = ref<Error | null>(null);
    const selectedCarbonReport = ref<CarbonReport | null>(null);

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

    /**
     * Single workspace/stats call backing the home load. The backend resolves
     * (or creates) the carbon report for `unitId`/`year` and returns the module
     * states, year config, and emission breakdown (with the validated-only
     * total merged in). Hydrates `selectedCarbonReport` here (pages sharing the
     * guard only ever read `.id` off it); the guard fans the rest out to the
     * timeline/module/yearConfig stores. Returns `null` on error (the global
     * http hook already toasts the user).
     */
    async function fetchWorkspaceHome(
      unitId: number,
      year: number,
    ): Promise<WorkspaceHomePayload | null> {
      try {
        carbonReportsLoading.value = true;
        carbonReportsError.value = null;
        const data = (await api
          .get(`workspace/${unitId}/${year}/home`)
          .json()) as WorkspaceHomePayload;
        selectedCarbonReport.value = {
          id: data.carbon_report_id,
          unit_id: unitId,
          year,
        };
        return data;
      } catch (error) {
        carbonReportsError.value =
          error instanceof Error
            ? error
            : new Error('Failed to load workspace');
        return null;
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
        // 404 is expected here — the catch branch creates the explore report.
        // Opt out of the global error toast for that status only.
        inv = await api.get(url, { skipErrorCodes: [404] }).json();
      } catch (err) {
        if (err instanceof HTTPError && err.response.status === 404) {
          // No explore report exists yet. It is created empty — the Explorer is
          // never seeded from the Calculator; only the Planner prefills.
          inv = await api.post(url).json();
        } else {
          throw err;
        }
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

    /** Apply an already-fetched units list (bootstrap / session). */
    function setUnits(newUnits: Unit[]) {
      units.value = newUnits || [];
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
        // 403/404 are expected — the unit guard probes units outside the
        // membership list (#2369) and redirects on refusal. No global toast.
        selectedUnit.value = (await api
          .get(`units/${id}`, { skipErrorCodes: [403, 404] })
          .json()) as Unit;
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
      setUnits,
      getUnit,
      getUnitResults,
      setUnit,
      setYear,
      setSelectedParams,
      // CarbonReport logic
      carbonReportsLoading,
      carbonReportsError,
      selectedCarbonReport,
      fetchWorkspaceHome,
      createCarbonReport,
      selectCarbonReportForYear,
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
