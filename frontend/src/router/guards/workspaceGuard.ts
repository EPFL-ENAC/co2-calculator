import type { RouteLocationNormalized } from 'vue-router';
import {
  useTimelineStore,
  useModuleStore,
  type CarbonReportModuleResponse,
} from 'src/stores/modules';
import {
  toEmissionBreakdown,
  type ReportStats,
} from 'src/utils/emissionStatsAdapter';
import { useSimulatorPlansStore } from 'src/stores/simulatorPlans';
import { useWorkspaceStore } from 'src/stores/workspace';
import {
  useYearConfigStore,
  type YearConfigurationResponse,
} from 'src/stores/yearConfig';
import { resolveLanguage } from 'src/utils/language';
import { resolveWorkspaceUnit } from 'src/utils/resolveWorkspaceUnit';
import {
  CARBON_PROJECT,
  resolveCarbonProject,
} from 'src/constant/carbon-project';
import {
  DEFAULT_ROUTE_NAME,
  WORKSPACE_ROUTE_NAME,
} from 'src/router/routeNames';

async function validateUnit() {
  const workspaceStore = useWorkspaceStore();
  const routeUnit = String(workspaceStore.selectedParams?.unit || '');
  // Membership list first; otherwise the backend decides (#2369) — global
  // roles may access units they are not members of.
  const validUnit = await resolveWorkspaceUnit(
    routeUnit,
    workspaceStore.units,
    async (id) => {
      await workspaceStore.getUnit(id);
      return workspaceStore.selectedUnit;
    },
  );

  if (validUnit) {
    workspaceStore.setUnit(validUnit);
    workspaceStore.setYear(workspaceStore.selectedParams?.year || null);
    return true;
  }
  // Backend refused (403/404) or the route unit is unparsable — fall back to
  // the landing resolver
  workspaceStore.setUnit(null);
  workspaceStore.setYear(null);
  return false;
}

/**
 * Shared workspace loader driven by the global `workspaceGuard`. Validates the
 * `:unit` param against the user's units, selects (or creates) the carbon
 * report for `:year`, loads the module states, and fetches the year
 * configuration. Returns `true` on success, or a redirect location back to the
 * landing resolver when the unit is invalid.
 */
export async function loadWorkspaceFromRoute(to: RouteLocationNormalized) {
  // Lighthouse CI bypass: skip unit validation so workspace pages render without a backend.
  if (window.__LIGHTHOUSE_BYPASS__) return true;

  // redirectToWorkspaceIfNotSelectedGuard
  useWorkspaceStore().setSelectedParams({
    year: parseInt(to.params.year as string, 10),
    unit: to.params.unit as string,
  });
  const workspaceStore = useWorkspaceStore();
  // Units are normally hydrated by the auth bootstrap (`GET /session`); refetch
  // only in the rare case the guard runs before they're available.
  if (workspaceStore.units.length === 0) {
    await workspaceStore.getUnits();
  }
  // Issue #1558 — `startedYears` (which years are open to users, driving the
  // WorkspaceSelectorBar year dropdown) can NOT be cached the same way as
  // `units` above: a backoffice admin can flip a year's `is_started` flag at
  // any point mid-session, so a once-per-bootstrap fetch goes stale the
  // moment that happens, and stays stale until a hard reload. Refetch it
  // unconditionally on every guard run instead — it's a cheap list call, the
  // same cost class as the `fetchWorkspaceHome` call below which already
  // refreshes on every run.
  await useYearConfigStore().fetchConfiguredYears();
  const response = await validateUnit();
  // if unit is valid retrieve carbon report  !
  let carbonReportId = null;
  if (response) {
    // One aggregate call replaces the old chain (report → module states → year
    // config → stats). It only re-runs on unit/year change, and pre-priming the
    // emission-breakdown cache also saves the Results page its own fetch.
    const data = await workspaceStore.fetchWorkspaceHome(
      workspaceStore.selectedUnit.id,
      workspaceStore.selectedYear,
    );
    carbonReportId = data?.carbon_report_id ?? null;
    if (data && carbonReportId) {
      // Fan the aggregate payload out into the per-concern stores so every
      // child page (home/module/results) reads it as if fetched individually.
      const moduleStates = (data.module_states ?? []) as {
        module_type_id: number;
        status: number;
      }[];
      useTimelineStore().setModuleStates(
        carbonReportId,
        moduleStates as CarbonReportModuleResponse[],
      );
      useYearConfigStore().setConfig(
        data.year_config as YearConfigurationResponse | null,
      );
      useModuleStore().setEmissionBreakdown(
        carbonReportId,
        toEmissionBreakdown(
          data.stats as unknown as ReportStats,
          [],
          moduleStates,
        ),
      );
      useSimulatorPlansStore().setPlans(data.project_plans ?? []);
    }
  }
  // then we can retrieve modules
  // Redirect when the unit itself is invalid, OR when it's valid but the
  // aggregate call failed/returned no report — otherwise navigation would
  // proceed into Home/Module/Results with the timeline, year-config, and
  // module stores never hydrated.
  if (!response || !carbonReportId) {
    return {
      name: DEFAULT_ROUTE_NAME,
      params: {
        language: resolveLanguage(to),
      },
      query: {
        unit: null,
        year: null,
      },
    };
  }
  return true;
}

/**
 * Global guard that keeps the selected workspace in sync with the route.
 *
 * Registered as a `beforeEach` (not a per-route `beforeEnter`) so it also fires
 * on param-only navigation — switching unit/year via the home-page dropdowns
 * only mutates route params and would otherwise never re-run a `beforeEnter`.
 */
export default async function workspaceGuard(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
) {
  // Only act on workspace routes (those nested under WORKSPACE_ROUTE_NAME).
  if (!to.matched.some((record) => record.name === WORKSPACE_ROUTE_NAME)) {
    return true;
  }
  // Nothing workspace-relevant changed (e.g. only :module or :language moved) —
  // skip the reload. On first entry `from` has no unit/year, so this differs
  // and the loader runs.
  //
  // Leaving a Simulator page (Explorer/Planner) for a Calculator route counts
  // as a change even on the same unit/year: those pages repoint
  // `selectedCarbonReport` and the emission breakdown at their own report, and
  // Calculator pages render straight from the stores without fetching.
  const returningToCalculator =
    resolveCarbonProject(to.meta) === CARBON_PROJECT.calculator &&
    resolveCarbonProject(from.meta) !== CARBON_PROJECT.calculator;
  if (
    to.params.unit === from.params.unit &&
    to.params.year === from.params.year &&
    !returningToCalculator
  ) {
    return true;
  }
  return loadWorkspaceFromRoute(to);
}
