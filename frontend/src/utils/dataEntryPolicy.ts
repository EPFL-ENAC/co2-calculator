/**
 * #951: per-row edit rights, keyed on a data entry's provenance.
 *
 * The backend (app.core.data_entry_permissions) hardcodes the actual field
 * matrix and ships it per submodule as `data_entry_policies`. This module
 * does NOT duplicate that matrix — it only buckets a row's `source` into
 * the policy branch key ("user"/"imported") the backend payload is keyed
 * by, matching `provenance_of()` on the backend exactly.
 */

export interface RowPolicy {
  create: boolean;
  delete: boolean;
  editable_fields: string[];
}

export interface DataEntryPolicies {
  user: RowPolicy;
  imported: RowPolicy;
}

export type DataEntryBranch = 'user' | 'imported';

// Mirrors backend/app/models/data_entry.py DataEntrySourceEnum values that
// app.core.data_entry_permissions._USER_BRANCH_SOURCES buckets into the
// "user" branch: USER_MANUAL (0), CSV/API_MODULE_UNIT_SPECIFIC (2/4 —
// #2453, an upload into one's OWN module is the operator's own data, same
// rights as manual entry; only backoffice per-year ingests are locked) and
// PLANNER_SNAPSHOT (6, Simulator Plan prefill — the user's own plan row).
// No shared source of truth for this bucketing (accepted tradeoff, see the
// #951 plan doc) — a new backend member meant to read as "user" needs this
// set updated too.
const USER_BRANCH_SOURCES = new Set([0, 2, 4, 6]);

export function branchOf(source: number | null | undefined): DataEntryBranch {
  return source == null || USER_BRANCH_SOURCES.has(source)
    ? 'user'
    : 'imported';
}

/**
 * `policies` is `null` for #951-exempt submodules (planner, embodied
 * energy — see backend SYSTEM_MANAGED_TYPES/is_planner_kind): no gating
 * applies there, mirroring the backend's own exemption rather than
 * mistaking absence for an empty allow-list.
 */
export function isFieldEditable(
  policies: DataEntryPolicies | null | undefined,
  source: number | null | undefined,
  fieldId: string,
): boolean {
  if (!policies) return true;
  return policies[branchOf(source)].editable_fields.includes(fieldId);
}

export function isRowDeletable(
  policies: DataEntryPolicies | null | undefined,
  source: number | null | undefined,
): boolean {
  if (!policies) return true;
  return policies[branchOf(source)].delete;
}
