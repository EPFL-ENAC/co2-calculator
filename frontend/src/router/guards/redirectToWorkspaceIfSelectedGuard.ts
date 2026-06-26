import type { RouteLocationNormalized } from 'vue-router';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { HOME_ROUTE_NAME, UNAUTHORIZED_ROUTE_NAME } from '../routeNames';

/**
 * Resolver for the parameterless landing route. The unified home page hosts the
 * Unit/Year dropdowns, so this guard's only job is to pick a default workspace
 * and forward to the home page:
 *
 *   1. A persisted selection (returning user) wins.
 *   2. Otherwise the first unit + most recent open year is chosen.
 *
 * When the account has no units there is nothing to show, so we forward to
 * /unauthorized. `validateUnitGuard` redirects here with `?unit&year` (both
 * null) when the persisted unit is no longer valid — that path resets the
 * selection first so we resolve a fresh default instead of looping back to the
 * stale unit.
 */
function unitSlug(id: number, name: string): string {
  return `${id}-${name.replace(/\s+/g, '-').toLowerCase()}`;
}

export default async function redirectToWorkspaceIfSelectedGuard(
  to: RouteLocationNormalized,
) {
  const workspaceStore = useWorkspaceStore();

  const forceReset = to.query.unit === null && to.query.year === null;
  if (forceReset) {
    workspaceStore.reset();
  } else if (workspaceStore.selectedParams) {
    return {
      name: HOME_ROUTE_NAME,
      params: {
        ...to.params,
        unit: encodeURIComponent(workspaceStore.selectedParams.unit),
        year: workspaceStore.selectedParams.year,
      },
    };
  }

  // Resolve a sensible default: first unit + most recent open year.
  await workspaceStore.getUnits();
  const unit = workspaceStore.units[0];
  if (!unit) return { name: UNAUTHORIZED_ROUTE_NAME }; // No units → not authorized.

  const yearConfigStore = useYearConfigStore();
  await Promise.all([
    workspaceStore.fetchCarbonReportsForUnit(unit.id),
    yearConfigStore.fetchConfiguredYears(),
  ]);

  const started = yearConfigStore.startedYears;
  const reportYears = workspaceStore.carbonReports.map((report) => report.year);
  const openYears = reportYears.filter((year) => started.has(year));
  const year =
    openYears.length > 0
      ? Math.max(...openYears)
      : reportYears.length > 0
        ? Math.max(...reportYears)
        : new Date().getFullYear() - 1;

  return {
    name: HOME_ROUTE_NAME,
    params: {
      ...to.params,
      unit: unitSlug(unit.id, unit.name),
      year: String(year),
    },
  };
}
