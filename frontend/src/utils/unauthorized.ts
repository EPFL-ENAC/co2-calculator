/**
 * Pure helpers for the "no workspace" flow (no assigned unit, or no
 * globally-open reporting year): the landing redirect and the /unauthorized
 * page message. Kept free of store/i18n imports so they stay unit-testable
 * without mounting Vue — importing a store would drag `src/i18n/index.ts`
 * (`import.meta.glob`) into the Playwright loader.
 */
import { UNAUTHORIZED_ROUTE_NAME } from 'src/router/routeNames';

/** Why a workspace can't be resolved: no assigned unit, or no globally-open year. */
export type NoWorkspaceReason = 'no-unit' | 'no-open-year';

/**
 * Where to send a user when no workspace can be resolved: /unauthorized, tagged
 * with `reason` so the page can explain the situation rather than showing a
 * bare 403. The page itself offers back-office users an escape button to the
 * back-office (where units are assigned and years are opened), so this resolver
 * stays permission-free. `/unauthorized` is a top-level route and needs no
 * `language` param.
 */
export function resolveNoWorkspaceRoute(reason: NoWorkspaceReason) {
  return { name: UNAUTHORIZED_ROUTE_NAME, query: { reason } };
}

/**
 * i18n key for the highlighted message shown on /unauthorized for a known
 * redirect `reason` (from `?reason=` query), or `null` when the reason is
 * absent/unrecognised (the page then falls back to the permission message or
 * the generic copy).
 */
const REASON_MESSAGE_KEYS: Record<NoWorkspaceReason, string> = {
  'no-unit': 'unauthorized_no_unit_message',
  'no-open-year': 'unauthorized_no_open_year_message',
};

function isNoWorkspaceReason(reason: string): reason is NoWorkspaceReason {
  return reason in REASON_MESSAGE_KEYS;
}

export function unauthorizedReasonMessageKey(
  reason: string | null,
): string | null {
  if (reason !== null && isNoWorkspaceReason(reason)) {
    return REASON_MESSAGE_KEYS[reason];
  }
  return null;
}
