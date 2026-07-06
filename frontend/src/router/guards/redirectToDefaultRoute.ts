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
 * Unit/Year dropdowns, so this guard's only job is to pick a default workspace —
 * the user's first unit + most recent open year — and forward to the home page,
 * or to {@link resolveNoUnitRoute} (back-office for admins, /unauthorized
 * otherwise) when the account has no units.
 */
export default async function redirectToDefaultRoute(
  to: RouteLocationNormalized,
) {
  const workspaceStore = useWorkspaceStore();

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
