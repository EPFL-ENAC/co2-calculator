/**
 * #951: per-row edit rights, keyed on a data entry's provenance.
 *
 * The backend (app.core.data_entry_permissions) hardcodes the actual field
 * matrix and ships it per submodule as `data_entry_policies`. This module
 * does NOT duplicate that matrix — it only buckets a row's `source` into
 * the policy branch key ("user"/"imported"/"reference") the backend payload
 * is keyed by, matching `provenance_of()` on the backend exactly.
 */

export interface RowPolicy {
  create: boolean;
  delete: boolean;
  editable_fields: string[];
}

export interface DataEntryPolicies {
  user: RowPolicy;
  imported: RowPolicy;
  /** #2646: a Simulator Plan row priced as a percentage of the reference year. */
  reference: RowPolicy;
}

export type DataEntryBranch = 'user' | 'imported' | 'reference';

/** The two row fields the branch is derived from. */
export interface PolicyRow {
  source?: number | null;
  percentage_of_reference_year?: number | null;
}

// Mirrors backend/app/models/data_entry.py DataEntrySourceEnum values that
// app.core.data_entry_permissions._USER_BRANCH_SOURCES buckets into the
// "user" branch: USER_MANUAL (0), CSV/API_MODULE_UNIT_SPECIFIC (2/4 —
// #2453, an upload into one's OWN module is the operator's own data, same
// rights as manual entry; only backoffice per-year ingests are locked) and
// PLANNER_SNAPSHOT (6, Simulator Plan prefill — the user's own plan row,
// unless it carries a percentage: see branchOf).
// No shared source of truth for this bucketing (accepted tradeoff, see the
// #951 plan doc) — a new backend member meant to read as "user" needs this
// set updated too.
const USER_BRANCH_SOURCES = new Set([0, 2, 4, 6]);

// DataEntrySourceEnum.PLANNER_SNAPSHOT.
const PLANNER_SNAPSHOT_SOURCE = 6;

// #2646: a planner snapshot row that carries a percentage is priced as
// reference kgCO2eq x percentage, never from its own fields, so the backend
// keeps only the percentage and the note writable on it. A snapshot row
// without one (professional travel's plain copy) stays "user".
export function branchOf(row: PolicyRow): DataEntryBranch {
  if (
    row.source === PLANNER_SNAPSHOT_SOURCE &&
    row.percentage_of_reference_year != null
  ) {
    return 'reference';
  }
  return row.source == null || USER_BRANCH_SOURCES.has(row.source)
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
  row: PolicyRow,
  fieldId: string,
): boolean {
  if (!policies) return true;
  return policies[branchOf(row)].editable_fields.includes(fieldId);
}

export function isRowDeletable(
  policies: DataEntryPolicies | null | undefined,
  row: PolicyRow,
): boolean {
  if (!policies) return true;
  return policies[branchOf(row)].delete;
}
