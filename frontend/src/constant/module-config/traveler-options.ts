import { MODULES } from 'src/constant/modules';

// "Other traveler" support for the Professional Travel module (issue #1153).
//
// Kept in a standalone module (importing only `src/constant/modules`) so the
// sentinel values and the pure `resolveTravelerName` resolver can be unit-tested
// without dragging in `src/utils/number` → `src/boot/i18n`, which uses the
// Vite-only `import.meta.glob` and breaks Playwright's node-side test collection.

// Sentinel `user_institutional_id` values for travelers not tied to a headcount
// member. Double-underscore namespacing signals "not a real SCIPER" and cannot
// collide with numeric EPFL SCIPERs.
// - INTERNAL: traveler has a SCIPER but is not in this unit's headcount.
// - EXTERNAL: traveler has no EPFL SCIPER at all.
export const TRAVELER_OTHER_INTERNAL = '__other_internal__';
export const TRAVELER_OTHER_EXTERNAL = '__other_external__';

// i18n keys for the labels of the two sentinel options (reused by the traveler
// dropdown and the table cell renderer).
export const TRAVELER_OTHER_INTERNAL_LABEL_KEY = `${MODULES.ProfessionalTravel}-field-traveler-other-internal`;
export const TRAVELER_OTHER_EXTERNAL_LABEL_KEY = `${MODULES.ProfessionalTravel}-field-traveler-other-external`;

/**
 * Resolve the display name for a travel row's traveler.
 *
 * `user_institutional_id` is the source of truth. Resolution order:
 * - null/absent → `'-'`.
 * - external sentinel → "Other traveler (external)".
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
  if (userInstitutionalId == null) return '-';
  if (userInstitutionalId === TRAVELER_OTHER_EXTERNAL) {
    return t(TRAVELER_OTHER_EXTERNAL_LABEL_KEY);
  }
  if (userInstitutionalId === TRAVELER_OTHER_INTERNAL) {
    return t(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
  }
  if (memberName) return memberName;
  return t(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
}
