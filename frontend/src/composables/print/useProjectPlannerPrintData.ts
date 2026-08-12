import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { api } from 'src/api/http';
import { getModuleTypeId } from 'src/constant/moduleStates';
import { MODULES } from 'src/constant/modules';
import {
  PLANNER_HEADCOUNT_CODES,
  PLANNER_HEADCOUNT_SUBMODULE,
} from 'src/constant/planner-headcount';
import type { EmissionBreakdownResponse } from 'src/stores/modules';
import {
  useSimulatorPlansStore,
  type SimulatorPlan,
  type SimulatorPlanYear,
} from 'src/stores/simulatorPlans';
import { useAuthStore } from 'src/stores/auth';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { sumBreakdownTonnes } from 'src/utils/breakdownTotal';
import {
  toEmissionBreakdown,
  type ReportStats,
} from 'src/utils/emissionStatsAdapter';
import { buildModulePath } from 'src/utils/modulePath';

export interface PlannerHeadcountRow {
  sius_code: string;
  fte: number;
}

/**
 * One sheet of the report. The list is built after fetching so a year with no
 * headcount never emits an empty page, and page numbers stay contiguous.
 */
export type PlannerPrintSheet =
  | { kind: 'year'; key: string; pageNumber: number; year: SimulatorPlanYear }
  | {
      kind: 'emissions';
      key: string;
      pageNumber: number;
      year: SimulatorPlanYear;
    }
  | {
      kind: 'headcount';
      key: string;
      pageNumber: number;
      year: SimulatorPlanYear;
    };

export function useProjectPlannerPrintData() {
  const route = useRoute();
  const authStore = useAuthStore();
  const workspaceStore = useWorkspaceStore();
  const plansStore = useSimulatorPlansStore();
  const yearConfigStore = useYearConfigStore();

  const loading = ref(true);
  const notFound = ref(false);
  const plan = ref<SimulatorPlan | null>(null);
  const headcountRows = ref<Record<number, PlannerHeadcountRow[]>>({});

  // Year pages and the range label cover the year sections; the Project
  // Grant report gets its own summary page (#1977).
  const planYears = computed(() =>
    plansStore.planYears.filter((year) => !year.is_grant),
  );

  const grantYear = computed(
    () => plansStore.planYears.find((year) => year.is_grant) ?? null,
  );

  const yearRangeLabel = computed(() => {
    const years = planYears.value;
    if (!years.length) return '';
    const first = years[0]?.year;
    const last = years[years.length - 1]?.year;
    return first === last ? `${first}` : `${first}–${last}`;
  });

  const scopeLabel = computed(() => {
    const unitName = workspaceStore.selectedUnit?.name ?? '';
    const range = yearRangeLabel.value;
    if (!range) return unitName;
    return unitName ? `${unitName} · ${range}` : range;
  });

  const planBreakdown = computed<EmissionBreakdownResponse | null>(() =>
    plansStore.aggregateStats
      ? toEmissionBreakdown(plansStore.aggregateStats)
      : null,
  );

  /** The Project Grant view, charted beside the year-by-year one (#1977). */
  const grantBreakdown = computed<EmissionBreakdownResponse | null>(() =>
    plansStore.grantStats ? toEmissionBreakdown(plansStore.grantStats) : null,
  );

  const totalTonnesCo2eq = computed(() =>
    sumBreakdownTonnes(planBreakdown.value),
  );

  const grantTotalTonnes = computed(() =>
    sumBreakdownTonnes(grantBreakdown.value),
  );

  /** Per-report breakdowns (years + grant), keyed by carbon report id. */
  const yearBreakdowns = computed<Record<number, EmissionBreakdownResponse>>(
    () => {
      const map: Record<number, EmissionBreakdownResponse> = {};
      for (const year of plansStore.planYears) {
        if (!year.stats) continue;
        map[year.id] = toEmissionBreakdown(
          year.stats as unknown as ReportStats,
        );
      }
      return map;
    },
  );

  function yearTotalTonnes(year: SimulatorPlanYear): number {
    return sumBreakdownTonnes(yearBreakdowns.value[year.id]);
  }

  /** Inactive modules are excluded from sums, graphs and results — and from the report. */
  function isHeadcountActive(year: SimulatorPlanYear): boolean {
    const entry = year.modules.find(
      (m) => m.module_type_id === getModuleTypeId(MODULES.Headcount),
    );
    return entry?.is_active ?? true;
  }

  /** The emission-type page only exists where the year has emissions to cut up. */
  function hasEmissionRows(year: SimulatorPlanYear): boolean {
    return (yearBreakdowns.value[year.id]?.module_breakdown ?? []).length > 0;
  }

  const sheets = computed<PlannerPrintSheet[]>(() => {
    const list: PlannerPrintSheet[] = [];
    // The cover is page 1.
    let pageNumber = 2;

    const pushReportSheets = (year: SimulatorPlanYear, prefix: string) => {
      list.push({
        kind: 'year',
        key: `${prefix}-${year.id}`,
        pageNumber: pageNumber++,
        year,
      });

      if (hasEmissionRows(year)) {
        list.push({
          kind: 'emissions',
          key: `emissions-${year.id}`,
          pageNumber: pageNumber++,
          year,
        });
      }
    };

    // The Project Grant summary leads, mirroring the planner page's
    // section order (#1977).
    if (grantYear.value) pushReportSheets(grantYear.value, 'grant');

    for (const year of planYears.value) {
      pushReportSheets(year, 'year');

      if (
        isHeadcountActive(year) &&
        (headcountRows.value[year.id] ?? []).length > 0
      ) {
        list.push({
          kind: 'headcount',
          key: `headcount-${year.id}`,
          pageNumber: pageNumber++,
          year,
        });
      }
    }

    return list;
  });

  async function initWorkspaceFromRoute(): Promise<boolean> {
    const unitParam = String(route.params.unit ?? '');
    const yearParam = parseInt(String(route.params.year ?? '0'), 10);

    workspaceStore.setSelectedParams({ unit: unitParam, year: yearParam });
    await workspaceStore.getUnits();

    const unitIdFromRoute = unitParam.split('-')[0];
    const validUnit = workspaceStore.units.find(
      (unit) =>
        unit.id === parseInt(unitIdFromRoute, 10) || unit.name === unitParam,
    );

    if (!validUnit) {
      workspaceStore.setUnit(null);
      workspaceStore.setYear(null);
      return false;
    }

    workspaceStore.setUnit(validUnit);
    workspaceStore.setYear(yearParam || null);
    return true;
  }

  async function fetchHeadcountRows(
    carbonReportId: number,
  ): Promise<PlannerHeadcountRow[]> {
    const response = await api
      .get(
        `${buildModulePath(
          MODULES.Headcount,
          carbonReportId,
        )}/${PLANNER_HEADCOUNT_SUBMODULE}?page=1&limit=100`,
      )
      .json<{ items: { sius_code?: string; fte?: number | null }[] }>();

    const byCode = new Map(
      response.items
        .filter((item) => item.sius_code)
        .map((item) => [item.sius_code as string, item]),
    );
    // A blank category is the plan saying "nobody here"; dropping it once means
    // neither the page list nor the table has to ask again what is filled in.
    const rows: PlannerHeadcountRow[] = [];
    for (const code of PLANNER_HEADCOUNT_CODES) {
      const fte = byCode.get(code)?.fte;
      if (fte != null) rows.push({ sius_code: code, fte });
    }
    return rows;
  }

  async function fetchAllData(): Promise<void> {
    loading.value = true;
    try {
      try {
        plan.value = await plansStore.getPlan(Number(route.params.planId));
      } catch {
        notFound.value = true;
        return;
      }

      await Promise.all([
        plansStore.fetchPlanYears(plan.value.id),
        plansStore.fetchAggregateStats(plan.value.id),
        yearConfigStore.fetchConfiguredYears(),
      ]);

      await Promise.all(
        planYears.value
          .filter(
            (year) =>
              isHeadcountActive(year) &&
              (year.is_grant ||
                authStore.canUserAccessModule(MODULES.Headcount)),
          )
          .map(async (year) => {
            try {
              headcountRows.value[year.id] = await fetchHeadcountRows(year.id);
            } catch {
              // An untouched module has no rows yet; leave the year without one.
              headcountRows.value[year.id] = [];
            }
          }),
      );
    } finally {
      loading.value = false;
    }
  }

  return {
    loading,
    notFound,
    plan,
    planYears,
    yearRangeLabel,
    scopeLabel,
    planBreakdown,
    grantBreakdown,
    totalTonnesCo2eq,
    grantTotalTonnes,
    yearBreakdowns,
    yearTotalTonnes,
    headcountRows,
    grantYear,
    sheets,
    initWorkspaceFromRoute,
    fetchAllData,
  };
}
