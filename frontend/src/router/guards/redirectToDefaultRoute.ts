import type { RouteLocationNormalized } from 'vue-router';
import { useWorkspaceStore, unitSlug } from '@/stores/workspace';
import { useYearConfigStore } from '@/stores/yearConfig';
import { resolveNoWorkspaceRoute } from '@/utils/unauthorized';
import { HOME_ROUTE_NAME } from '../routeNames';

/**
 * The set of globally-open (`is_started`) years. Issue #1558 — unlike `units`
 * below, this can go stale mid-session: a backoffice admin can open a year at
 * any time, and a once-per-bootstrap fetch would keep sending returning users
 * to /unauthorized (or the wrong default year) until a hard reload. Always
 * refetch, so this resolver reflects the current backend state on every
 * landing-route hit.
 */
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
 * or to {@link resolveNoWorkspaceRoute} (/unauthorized, tagged with why — the
 * page offers back-office users an escape button) when there's no unit or no
 * open year.
 */
export default async function redirectToDefaultRoute(
  to: RouteLocationNormalized,
) {
  const workspaceStore = useWorkspaceStore();

  // Units are normally hydrated by the auth bootstrap (`GET /session`), which
  // `authGuard` awaits before this resolver ever runs; refetch only in the
  // rare case the guard runs before they're available.
  if (workspaceStore.units.length === 0) {
    await workspaceStore.getUnits();
  }
  const unit = workspaceStore.units[0];
  if (!unit) {
    return resolveNoWorkspaceRoute('no-unit');
  }

  const startedYears = await fetchStartedYears();
  if (startedYears.size === 0) return resolveNoWorkspaceRoute('no-open-year');

  return {
    name: HOME_ROUTE_NAME,
    params: {
      ...to.params,
      unit: unitSlug(unit),
      year: String(pickDefaultYear(startedYears)),
    },
  };
}
