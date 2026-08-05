import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { api } from 'src/api/http';
import type { Submodule } from 'src/constant/moduleConfig';
import { getModuleTypeId } from 'src/constant/moduleStates';
import {
  MODULES,
  enumSubmodule,
  type EnumSubmoduleType,
  type Module,
} from 'src/constant/modules';
import {
  PLANNER_HEADCOUNT_SUBMODULE,
  PLANNER_SIUS_CODES,
} from 'src/constant/planner-headcount';
import type { EmissionBreakdownResponse } from 'src/stores/modules';
import { useModuleStore } from 'src/stores/modules';
import {
  useSimulatorPlansStore,
  type SimulatorPlan,
  type SimulatorPlanYear,
} from 'src/stores/simulatorPlans';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { sumBreakdownTonnes } from 'src/utils/breakdownTotal';
import {
  toEmissionBreakdown,
  type ReportStats,
} from 'src/utils/emissionStatsAdapter';
import { buildModulePath } from 'src/utils/modulePath';
import {
  getPlannerPrintModules,
  type PlannerPrintModule,
} from 'src/utils/plannerPrintModules';
import { fetchAllSubmoduleRows } from 'src/utils/printSubmoduleRows';
import type { PrintRow } from 'src/utils/printTable';

export interface PlannerHeadcountRow {
  sius_code: string;
  fte: number;
}

/** One printable submodule table: its config and the rows to draw. */
export interface PlannerPrintTable {
  sub: Submodule;
  rows: PrintRow[];
}

/**
 * One sheet of the report. The list is built after fetching so modules with no
 * rows in a given year never emit an empty page, and page numbers stay
 * contiguous.
 */
export type PlannerPrintSheet =
  | { kind: 'year'; key: string; pageNumber: number; year: SimulatorPlanYear }
  | {
      kind: 'headcount';
      key: string;
      pageNumber: number;
      year: SimulatorPlanYear;
    }
  | {
      kind: 'module';
      key: string;
      pageNumber: number;
      year: SimulatorPlanYear;
      module: PlannerPrintModule;
    };

/** Rows are addressed per plan-year report, since a submodule repeats each year. */
function rowsKey(carbonReportId: number, submoduleId: string): string {
  return `${carbonReportId}:${submoduleId}`;
}

/** Counts are addressed per plan-year report and module. */
function countsKey(carbonReportId: number, moduleType: Module): string {
  return `${carbonReportId}:${moduleType}`;
}

/**
 * A plan report fans out to years × modules × submodules, so a ten-year plan
 * would open well over a hundred requests at once — past the browser's
 * per-host connection limit, where the tail just queues anyway.
 */
const FETCH_CONCURRENCY = 6;

/**
 * Count probes read no rows and write no audit records, so they neither trip
 * the same-module conflict nor cost much per request; they can fan out wider.
 */
const PROBE_CONCURRENCY = 12;

async function runPooled(
  tasks: (() => Promise<unknown>)[],
  concurrency = FETCH_CONCURRENCY,
): Promise<void> {
  let cursor = 0;
  const workers = Array.from(
    { length: Math.min(concurrency, tasks.length) },
    async () => {
      for (;;) {
        const task = tasks[cursor++];
        if (!task) return;
        await task();
      }
    },
  );
  await Promise.all(workers);
}

export function useProjectPlannerPrintData() {
  const route = useRoute();
  const workspaceStore = useWorkspaceStore();
  const moduleStore = useModuleStore();
  const plansStore = useSimulatorPlansStore();
  const yearConfigStore = useYearConfigStore();

  const loading = ref(true);
  const notFound = ref(false);
  const plan = ref<SimulatorPlan | null>(null);
  const submoduleRows = ref<Record<string, PrintRow[]>>({});
  const headcountRows = ref<Record<number, PlannerHeadcountRow[]>>({});
  /** "module · year" for every table that failed to load, named on the cover. */
  const incompleteModules = ref<string[]>([]);

  const printModules = getPlannerPrintModules();

  // The Project Grant report stays out of the printed report until #1977
  // settles how grant results combine with the per-year results.
  const planYears = computed(() =>
    plansStore.planYears.filter((year) => !year.is_grant),
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

  const totalTonnesCo2eq = computed(() =>
    sumBreakdownTonnes(planBreakdown.value),
  );

  /** Per-year breakdowns, keyed by the plan-year carbon report id. */
  const yearBreakdowns = computed<Record<number, EmissionBreakdownResponse>>(
    () => {
      const map: Record<number, EmissionBreakdownResponse> = {};
      for (const year of planYears.value) {
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
  function isModuleActive(
    year: SimulatorPlanYear,
    module: PlannerPrintModule | typeof MODULES.Headcount,
  ): boolean {
    const moduleType = typeof module === 'string' ? module : module.type;
    const entry = year.modules.find(
      (m) => m.module_type_id === getModuleTypeId(moduleType),
    );
    return entry?.is_active ?? true;
  }

  /**
   * The tables to print for one module in one plan-year. Submodules the plan
   * never touched are dropped here, so both the page list and the page itself
   * read the same answer instead of each re-deciding what is empty.
   */
  function moduleTables(
    year: SimulatorPlanYear,
    module: PlannerPrintModule,
  ): PlannerPrintTable[] {
    return module.submodules
      .map((sub) => ({
        sub,
        rows: submoduleRows.value[rowsKey(year.id, sub.id)] ?? [],
      }))
      .filter((table) => table.rows.length > 0);
  }

  const sheets = computed<PlannerPrintSheet[]>(() => {
    const list: PlannerPrintSheet[] = [];
    // The cover is page 1.
    let pageNumber = 2;

    for (const year of planYears.value) {
      list.push({
        kind: 'year',
        key: `year-${year.id}`,
        pageNumber: pageNumber++,
        year,
      });

      if (
        isModuleActive(year, MODULES.Headcount) &&
        (headcountRows.value[year.id] ?? []).length > 0
      ) {
        list.push({
          kind: 'headcount',
          key: `headcount-${year.id}`,
          pageNumber: pageNumber++,
          year,
        });
      }

      for (const module of printModules) {
        if (!isModuleActive(year, module)) continue;
        if (moduleTables(year, module).length === 0) continue;
        list.push({
          kind: 'module',
          key: `module-${year.id}-${module.type}`,
          pageNumber: pageNumber++,
          year,
          module,
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
    for (const code of PLANNER_SIUS_CODES) {
      const fte = byCode.get(code)?.fte;
      if (fte != null) rows.push({ sius_code: code, fte });
    }
    return rows;
  }

  /**
   * How many rows each submodule of one module holds in one plan-year, in a
   * single request. A planner module owns up to eight submodules and a plan
   * typically fills two or three, so asking the module once beats asking every
   * submodule for a page of rows it does not have.
   */
  async function fetchSubmoduleCounts(
    carbonReportId: number,
    moduleType: Module,
  ): Promise<Record<number, number>> {
    const response = await api
      .get(`${buildModulePath(moduleType, carbonReportId)}?preview_limit=0`)
      .json<{ data_entry_types_total_items?: Record<number, number> }>();
    return response.data_entry_types_total_items ?? {};
  }

  /**
   * Planner factors resolve from each year's reference year, so taxonomy labels
   * are fetched against the first baseline the plan actually uses. The store
   * keys taxonomies by submodule alone; one fetch per submodule is all it holds.
   */
  function taxonomyTasks(
    taxonomyYear: number | null,
    submodules: { module: PlannerPrintModule; sub: Submodule }[],
  ): (() => Promise<unknown>)[] {
    if (taxonomyYear == null) return [];
    return submodules
      .filter(({ sub }) =>
        sub.moduleFields.some((field) => field.optionsId === 'kind'),
      )
      .map(
        ({ module, sub }) =>
          () =>
            moduleStore.getSubmoduleTaxonomy(
              module.type,
              sub.id,
              String(taxonomyYear),
            ),
      );
  }

  async function fetchAllData(): Promise<void> {
    loading.value = true;
    try {
      const unitId = workspaceStore.selectedUnit?.id;
      if (unitId == null) {
        notFound.value = true;
        return;
      }

      try {
        plan.value = await plansStore.getPlanByName(
          unitId,
          String(route.params.name),
        );
      } catch {
        notFound.value = true;
        return;
      }

      await Promise.all([
        plansStore.fetchPlanYears(plan.value.id),
        plansStore.fetchAggregateStats(plan.value.id),
        yearConfigStore.fetchConfiguredYears(),
      ]);

      const years = planYears.value;
      const taxonomyYear =
        years.find((year) => year.reference_year != null)?.reference_year ??
        plan.value.default_factor_year ??
        years[0]?.year ??
        null;

      const activePairs = years.flatMap((year) =>
        printModules
          .filter((module) => isModuleActive(year, module))
          .map((module) => ({ year, module })),
      );

      // Pass 1 — ask each module-year which of its submodules hold anything.
      const counts: Record<string, Record<number, number>> = {};
      await runPooled(
        activePairs.map(({ year, module }) => async () => {
          try {
            counts[countsKey(year.id, module.type)] =
              await fetchSubmoduleCounts(year.id, module.type);
          } catch {
            // Leave it unknown: pass 2 then fetches the module's submodules.
          }
        }),
        PROBE_CONCURRENCY,
      );

      // Pass 2 — fetch only the tables the report will actually draw.
      const tasks: (() => Promise<unknown>)[] = [];
      const taxonomySubmodules = new Map<
        string,
        { module: PlannerPrintModule; sub: Submodule }
      >();

      for (const year of years) {
        if (isModuleActive(year, MODULES.Headcount)) {
          tasks.push(async () => {
            try {
              headcountRows.value[year.id] = await fetchHeadcountRows(year.id);
            } catch {
              // An untouched module has no rows yet; leave the year without one.
              headcountRows.value[year.id] = [];
            }
          });
        }
      }

      for (const { year, module } of activePairs) {
        // A failed probe or a submodule the enum does not know reads as "fetch
        // it": a table dropped on a missing answer is a silently short report.
        const filled = module.submodules.filter((sub) => {
          const moduleCounts = counts[countsKey(year.id, module.type)];
          if (!moduleCounts) return true;
          const typeId = enumSubmodule[sub.id as EnumSubmoduleType];
          return typeId == null || (moduleCounts[typeId] ?? 0) > 0;
        });
        if (!filled.length) continue;
        for (const sub of filled) {
          taxonomySubmodules.set(`${module.type}:${sub.id}`, { module, sub });
        }
        // One task per module, walking its submodules in series: concurrent
        // reads of the same module on one report make the backend 500.
        tasks.push(async () => {
          for (const sub of filled) {
            try {
              submoduleRows.value[rowsKey(year.id, sub.id)] =
                await fetchAllSubmoduleRows(module.type, sub.id, year.id);
            } catch {
              // A report that drops a table without saying so is worse than
              // one that admits the gap.
              incompleteModules.value.push(`${module.type} · ${year.year}`);
            }
          }
        });
      }

      tasks.push(
        ...taxonomyTasks(taxonomyYear, [...taxonomySubmodules.values()]),
      );

      await runPooled(tasks);
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
    totalTonnesCo2eq,
    yearBreakdowns,
    yearTotalTonnes,
    headcountRows,
    incompleteModules,
    sheets,
    moduleTables,
    initWorkspaceFromRoute,
    fetchAllData,
  };
}
