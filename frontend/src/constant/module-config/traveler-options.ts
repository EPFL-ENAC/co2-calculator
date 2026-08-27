import { MODULES } from '@/constant/modules';

// "Other traveler" support for the Professional Travel module (issue #1153).
//
// Kept in a standalone module (importing only `src/constant/modules`) so the
// sentinel values and the pure `resolveTravelerName` resolver can be unit-tested
// without dragging in `src/utils/number` → `src/boot/i18n`, which uses the
// Vite-only `import.meta.glob` and breaks Playwright's node-side test collection.

// Sentinel `user_institutional_id` values for travelers not tied to a headcount
// member. Backend task #1153 switched from string sentinels to `-1` (internal) and
// `null` (external), matching the backend's database representation.
// - INTERNAL: traveler has a SCIPER but is not in this unit's headcount.
// - EXTERNAL: traveler has no EPFL SCIPER at all.
export const TRAVELER_OTHER_INTERNAL = '-1';
export const TRAVELER_OTHER_EXTERNAL = null;

// i18n keys for the labels of the two sentinel options (reused by the traveler
// dropdown and the table cell renderer).
export const TRAVELER_OTHER_INTERNAL_LABEL_KEY = `${MODULES.ProfessionalTravel}-field-traveler-other-internal`;
export const TRAVELER_OTHER_EXTERNAL_LABEL_KEY = `${MODULES.ProfessionalTravel}-field-traveler-other-external`;

/**
 * Resolve the display name for a travel row's traveler.
 *
 * `user_institutional_id` is the source of truth. Resolution order:
 * - undefined ("no data yet") → `'-'`.
 * - null (external sentinel) → "Other traveler (external)".
 * - internal sentinel → "Other traveler (internal)".
 * - a SCIPER matching a headcount member → that member's name.
 * - any other SCIPER (imported, not in this unit's headcount) → "Other traveler
 *   (internal)" — it has a SCIPER, and such rows must still surface (not blank).
 *
 * @param memberName the headcount name already looked up for this SCIPER, if any.
 * @param t an i18n translate function (key → localized string).
 */
export function resolveTravelerName(
  userInstitutionalId: string | null | undefined,
  memberName: string | undefined,
  t: (key: string) => string,
): string {
  // Only "no data yet" renders a dash. Once External other is a real
  // `null`, a loose `== null` here would swallow it too — use `===`.
  if (userInstitutionalId === undefined) return '-';
  if (userInstitutionalId === TRAVELER_OTHER_EXTERNAL) {
    return t(TRAVELER_OTHER_EXTERNAL_LABEL_KEY);
  }
  if (userInstitutionalId === TRAVELER_OTHER_INTERNAL) {
    return t(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
  }
  if (memberName) return memberName;
  return t(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
}

/**
 * Resolve the traveler_name table-cell text for a Professional Travel row
 * (extracted from ModuleTable.vue's renderCell so it's unit-testable
 * without mounting the component). Precedence: no data yet → dash; roster
 * match → member name; the viewer's own id → their display name (covers
 * standard users whose roster map may not include themselves); otherwise
 * delegate to resolveTravelerName for the sentinel/unresolved-SCIPER cases.
 */
export function resolveTravelerCellText(
  userInstitutionalId: string | null | undefined,
  headcountMembersMap: Map<string, string>,
  currentUserInstitutionalId: string | null | undefined,
  currentUserDisplayName: string,
  t: (key: string) => string,
): string {
  if (userInstitutionalId === undefined) return '-';
  if (userInstitutionalId !== null) {
    const member = headcountMembersMap.get(userInstitutionalId);
    if (member) return member;
    if (userInstitutionalId === currentUserInstitutionalId) {
      return currentUserDisplayName;
    }
  }
  return resolveTravelerName(userInstitutionalId, undefined, t);
}

/**
 * Legend entries for the trips-map "Other traveler" sentinels
 * (ModuleCharts.vue). get_professional_travel_trips_map coerces a null
 * SCIPER to "" server-side (`tid = traveler_id or ""`, data_entry_repo.py)
 * — that endpoint never sees TRAVELER_OTHER_EXTERNAL's real null, so the
 * legend must be keyed to what it actually emits.
 */
export function travelerSentinelMapEntries(
  t: (key: string) => string,
): [string, string][] {
  return [
    [TRAVELER_OTHER_INTERNAL, t(TRAVELER_OTHER_INTERNAL_LABEL_KEY)],
    ['', t(TRAVELER_OTHER_EXTERNAL_LABEL_KEY)],
  ];
}
