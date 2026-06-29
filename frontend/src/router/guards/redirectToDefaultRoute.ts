import type { RouteLocationNormalized } from 'vue-router';
import { useWorkspaceStore, unitSlug } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { HOME_ROUTE_NAME, UNAUTHORIZED_ROUTE_NAME } from '../routeNames';

/**
 * `workspaceGuard` redirects here with `?unit&year` (both null) when a persisted
 * unit is no longer valid. That signals we must drop the stale selection and
 * resolve a fresh default instead of honouring (and looping back to) it.
 */
function isForcedReset(to: RouteLocationNormalized): boolean {
  return to.query.unit === null && to.query.year === null;
}

/** The home route a returning user's persisted selection points at, if any. */
function persistedHomeRoute(to: RouteLocationNormalized) {
  const { selectedParams } = useWorkspaceStore();
  if (!selectedParams) return null;

  return {
    name: HOME_ROUTE_NAME,
    params: {
      ...to.params,
      unit: encodeURIComponent(selectedParams.unit),
      year: selectedParams.year,
    },
  };
}

/** Fetch the unit's carbon reports and the globally configured (open) years. */
async function fetchYearData(unitId: number) {
  const workspaceStore = useWorkspaceStore();
  const yearConfigStore = useYearConfigStore();

  await Promise.all([
    workspaceStore.fetchCarbonReportsForUnit(unitId),
    yearConfigStore.fetchConfiguredYears(),
  ]);

  return {
    reportYears: workspaceStore.carbonReports.map((report) => report.year),
    startedYears: yearConfigStore.startedYears,
  };
}

/**
 * Pick the year to land on, preferring the most recent year that is both
 * reported and still open for editing, then the most recent reported year, and
 * finally last calendar year when the unit has no reports at all.
 */
function pickDefaultYear(
  reportYears: number[],
  startedYears: Set<number>,
): number {
  const openYears = reportYears.filter((year) => startedYears.has(year));
  if (openYears.length > 0) return Math.max(...openYears);
  if (reportYears.length > 0) return Math.max(...reportYears);
  return new Date().getFullYear() - 1;
}

/**
 * Resolver for the parameterless landing route. The unified home page hosts the
 * Unit/Year dropdowns, so this guard's only job is to pick a default workspace
 * and forward to the home page:
 *
 *   1. A persisted selection (returning user) wins.
 *   2. Otherwise the first unit + most recent open year is chosen.
 *
 * When the account has no units there is nothing to show, so we forward to
 * /unauthorized.
 */
export default async function redirectToDefaultRoute(
  to: RouteLocationNormalized,
) {
  const workspaceStore = useWorkspaceStore();

  if (isForcedReset(to)) {
    workspaceStore.reset();
  } else {
    const persisted = persistedHomeRoute(to);
    if (persisted) return persisted;
  }

  await workspaceStore.getUnits();
  const unit = workspaceStore.units[0];
  if (!unit) return { name: UNAUTHORIZED_ROUTE_NAME }; // No units → not authorized.

  const { reportYears, startedYears } = await fetchYearData(unit.id);
  const year = pickDefaultYear(reportYears, startedYears);

  return {
    name: HOME_ROUTE_NAME,
    params: {
      ...to.params,
      unit: unitSlug(unit),
      year: String(year),
    },
  };
}
