import type { RouteLocationNormalized } from 'vue-router';
import { useWorkspaceStore, unitSlug } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useAuthStore, PermissionAction } from 'src/stores/auth';
import {
  resolveNoUnitRoute,
  resolveNoOpenYearRoute,
} from 'src/utils/unauthorized';
import { currentLanguage } from 'src/utils/language';
import { HOME_ROUTE_NAME } from '../routeNames';

/**
 * The global `workspaceGuard` (beforeEach in ./workspaceGuard.ts) redirects to
 * this landing route with `?unit=&year=` (both null) when the route's `:unit`
 * isn't one of the user's units — see `loadWorkspaceFromRoute`'s
 * DEFAULT_ROUTE_NAME redirect. This is the receiving end of that signal: the
 * null query tells us to drop the stale persisted selection and resolve a fresh
 * default, instead of honouring it (which would just loop back to the bad unit).
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

/** The set of globally-open (`is_started`) years. */
async function fetchStartedYears(): Promise<Set<number>> {
  const yearConfigStore = useYearConfigStore();
  await yearConfigStore.fetchConfiguredYears();
  return yearConfigStore.startedYears;
}

/**
 * The year a fresh workspace lands on: the most recent globally-open year. The
 * workspace guard selects-or-creates the carbon report for it on arrival, so a
 * report need not already exist. Callers must pass a non-empty set — the landing
 * guard redirects to /unauthorized before reaching here when no year is open.
 */
export function pickDefaultYear(startedYears: Set<number>): number {
  return Math.max(...startedYears);
}

/**
 * Resolver for the parameterless landing route. The unified home page hosts the
 * Unit/Year dropdowns, so this guard's only job is to pick a default workspace
 * and forward to the home page:
 *
 *   1. A persisted selection (returning user) wins.
 *   2. Otherwise the first unit + most recent open year is chosen.
 *   3. No units → forward via {@link resolveNoUnitRoute} (back-office for
 *      admins, /unauthorized otherwise).
 */
export default async function redirectToDefaultRoute(
  to: RouteLocationNormalized,
) {
  const workspaceStore = useWorkspaceStore();

  // Returning user: honour the persisted selection. If its unit is stale, the
  // workspace guard validates it, fails, and bounces back here with a forced
  // reset — so there's no need to pre-validate units on this path.
  if (!isForcedReset(to)) {
    const persisted = persistedHomeRoute(to);
    if (persisted) return persisted;
  }

  // Fresh resolve (no persisted selection, or a forced reset): drop stale
  // state and route by unit membership.
  workspaceStore.reset();
  await workspaceStore.getUnits();
  const unit = workspaceStore.units[0];
  if (!unit) {
    const canAccessBackOfficeConfig = useAuthStore().hasUserAnyScopePermission(
      'backoffice.configuration',
      PermissionAction.EDIT,
    );
    return resolveNoUnitRoute(
      canAccessBackOfficeConfig,
      String(to.params.language ?? currentLanguage()),
    );
  }

  const startedYears = await fetchStartedYears();
  if (startedYears.size === 0) return resolveNoOpenYearRoute();

  return {
    name: HOME_ROUTE_NAME,
    params: {
      ...to.params,
      unit: unitSlug(unit),
      year: String(pickDefaultYear(startedYears)),
    },
  };
}
