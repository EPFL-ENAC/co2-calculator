import type { RouteLocationNormalized } from 'vue-router';
import { useTimelineStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { resolveLanguage } from 'src/utils/language';
import {
  DEFAULT_ROUTE_NAME,
  WORKSPACE_ROUTE_NAME,
} from 'src/router/routeNames';

async function validateUnit() {
  const workspaceStore = useWorkspaceStore();
  const routeUnit = String(workspaceStore.selectedParams?.unit || '');
  const unitIdFromRoute = routeUnit.split('-')[0];
  const validUnit = workspaceStore.units.find(
    (unit) =>
      unit.id === parseInt(unitIdFromRoute, 10) || unit.name === routeUnit,
  );

  if (validUnit) {
    workspaceStore.setUnit(validUnit);
    workspaceStore.setYear(workspaceStore.selectedParams?.year || null);
    return true;
  }
  // If the unit from the route is not valid, fall back to the landing resolver
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
  await workspaceStore.getUnits();
  const response = await validateUnit();
  // if unit is valid retrieve carbon report  !
  let carbonReportId = null;
  if (response) {
    await workspaceStore.selectCarbonReportForYear(
      workspaceStore.selectedUnit.id,
      workspaceStore.selectedYear,
    );
    carbonReportId = workspaceStore.selectedCarbonReport?.id;
    if (carbonReportId) {
      const timelineStore = useTimelineStore();
      await timelineStore.fetchModuleStates(carbonReportId);
    }
    // Load the year configuration for the now-selected workspace year so every
    // child page (home/module/results) has it ready.
    await useYearConfigStore().fetchConfig(workspaceStore.selectedYear);
  }
  // then we can retrieve modules
  if (!response && !carbonReportId) {
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
 * This replaces the former `WorkspacePage` layout component, whose `onMounted`
 * + `onBeforeRouteUpdate` existed solely to run this logic.
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
  if (
    to.params.unit === from.params.unit &&
    to.params.year === from.params.year
  ) {
    return true;
  }
  return loadWorkspaceFromRoute(to);
}
