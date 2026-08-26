/**
 * Resolve the workspace unit for a route `:unit` param (#2369).
 *
 * The membership list (`GET users/units`) is only a fast path — it is NOT the
 * authorization boundary. When the route's unit is not in the list (e.g. a
 * global-scope role opening a unit it is not a member of), the backend is
 * asked for that unit and decides access: a unit on 200 → proceed, null
 * (403/404) → the caller redirects. The frontend never checks roles.
 *
 * Kept as a pure leaf helper (no store/api imports) so the regression test in
 * `tests/unit/validate-unit-resolution.spec.ts` can run node-side under
 * Playwright without dragging in the Pinia/i18n boot chain.
 */
export async function resolveWorkspaceUnit<
  U extends { id: number; name: string },
>(
  routeUnit: string,
  memberUnits: U[],
  fetchUnit: (id: number) => Promise<U | null>,
): Promise<U | null> {
  const unitId = parseInt(routeUnit.split('-')[0], 10);
  const memberUnit = memberUnits.find(
    (unit) => unit.id === unitId || unit.name === routeUnit,
  );
  if (memberUnit) return memberUnit;
  if (Number.isNaN(unitId)) return null;
  return fetchUnit(unitId);
}
