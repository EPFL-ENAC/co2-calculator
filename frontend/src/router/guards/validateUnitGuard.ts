import type { RouteLocationNormalized } from 'vue-router';
import { useTimelineStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { DEFAULT_ROUTE_NAME } from '../routeNames';

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
 * Shared workspace loader used by both the route `beforeEnter` guard and
 * `WorkspacePage`'s `onBeforeRouteUpdate`. Validates the `:unit` param against
 * the user's units, selects (or creates) the carbon report for `:year`, and
 * loads the module states. Returns `true` on success, or a redirect location
 * back to the landing resolver when the unit is invalid.
 *
 * Keeping this in one place ensures switching unit/year via the home-page
 * dropdowns — which only mutates route params and therefore does NOT re-run
 * `beforeEnter` — still refreshes the selected workspace.
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
  }
  // then we can retrieve modules
  if (!response && !carbonReportId) {
    return {
      name: DEFAULT_ROUTE_NAME,
      params: {
        language: to.params.language || 'en',
      },
      query: {
        unit: null,
        year: null,
      },
    };
  }
  return true;
}

export default async function validateUnitGuard(to: RouteLocationNormalized) {
  return loadWorkspaceFromRoute(to);
}
