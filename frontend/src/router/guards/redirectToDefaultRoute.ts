import type { RouteLocationNormalized } from 'vue-router';
import { useWorkspaceStore, unitSlug } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useAuthStore, PermissionAction } from 'src/stores/auth';
import { resolveNoUnitRoute } from 'src/utils/unauthorized';
import { currentLanguage } from 'src/utils/language';
import { HOME_ROUTE_NAME } from '../routeNames';

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
 *   1. No units → forward via {@link resolveNoUnitRoute} (back-office for
 *      admins, /unauthorized otherwise). Checked first so a stale persisted
 *      selection can never route a unitless account into a workspace page.
 *   2. Otherwise a persisted selection (returning user) wins.
 *   3. Otherwise the first unit + most recent open year is chosen.
 */
export default async function redirectToDefaultRoute(
  to: RouteLocationNormalized,
) {
  const workspaceStore = useWorkspaceStore();

  if (isForcedReset(to)) {
    workspaceStore.reset();
  }

  // Resolve the user's units up front. A no-unit account must always be routed
  // by unit membership, never by a persisted selection: `selectedParams` is
  // persisted to localStorage, so a stale value from a prior session would
  // otherwise forward a now-unitless user to a workspace route that 403s.
  await workspaceStore.getUnits();
  const unit = workspaceStore.units[0];
  if (!unit) {
    // Drop any stale persisted selection so the next entry doesn't loop, then
    // send users who can reach the back-office config page there, and everyone
    // else (including back-office users without configuration access) to a "not
    // assigned to a unit" explanation on /unauthorized. Gate on the exact
    // permission the target page requires — `backoffice.configuration` edit,
    // matching the `backoffice-data-management` route meta — so we never
    // forward to a page `permissionGuard` would bounce to a generic 403. The
    // landing route is under `:language`, so `to.params.language` is present.
    workspaceStore.reset();
    const canAccessBackOfficeConfig = useAuthStore().hasUserAnyScopePermission(
      'backoffice.configuration',
      PermissionAction.EDIT,
    );
    return resolveNoUnitRoute(
      canAccessBackOfficeConfig,
      String(to.params.language ?? currentLanguage()),
    );
  }

  // The user has at least one unit: honour a persisted selection (returning
  // user) before falling back to their first unit + most recent open year.
  if (!isForcedReset(to)) {
    const persisted = persistedHomeRoute(to);
    if (persisted) return persisted;
  }

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
