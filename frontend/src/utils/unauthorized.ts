/**
 * Pure helpers for the "no assigned unit" flow (landing redirect + the
 * /unauthorized page message). Kept free of store/i18n imports so they stay
 * unit-testable without mounting Vue — importing a store would drag
 * `src/i18n/index.ts` (`import.meta.glob`) into the Playwright loader.
 */
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import { UNAUTHORIZED_ROUTE_NAME } from 'src/router/routeNames';

/**
 * Where a user with no assigned unit should land. A user who can reach the
 * back-office configuration page has a legitimate destination there, so they go
 * straight to it. Everyone else — including back-office users WITHOUT
 * configuration access — stays on /unauthorized, tagged so the page can explain
 * that the account is simply not assigned to a unit rather than showing a bare
 * 403. (`canAccessBackOfficeConfig` must reflect the config page's own
 * permission gate, or we'd forward to a page that just bounces to a 403.)
 *
 * The back-office page lives under the `:language` segment, so its redirect must
 * carry the current `language` param; `/unauthorized` is a top-level route and
 * needs none.
 */
export function resolveNoUnitRoute(
  canAccessBackOfficeConfig: boolean,
  language: string,
) {
  if (canAccessBackOfficeConfig) {
    return {
      name: BACKOFFICE_NAV.BACKOFFICE_DATA_MANAGEMENT.routeName,
      params: { language },
    };
  }
  return { name: UNAUTHORIZED_ROUTE_NAME, query: { reason: 'no-unit' } };
}

/**
 * Where to send a user when no reporting year is globally open, so there's no
 * workspace to resolve a default year for. `/unauthorized` is a top-level route
 * and needs no `language` param.
 */
export function resolveNoOpenYearRoute() {
  return { name: UNAUTHORIZED_ROUTE_NAME, query: { reason: 'no-open-year' } };
}

/**
 * i18n key for the highlighted message shown on /unauthorized for a known
 * redirect `reason` (from `?reason=` query), or `null` when the reason is
 * absent/unrecognised (the page then falls back to the permission message or
 * the generic copy).
 */
export function unauthorizedReasonMessageKey(
  reason: string | null,
): string | null {
  if (reason === 'no-unit') return 'unauthorized_no_unit_message';
  if (reason === 'no-open-year') return 'unauthorized_no_open_year_message';
  return null;
}
