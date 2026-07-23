/**
 * The 8 backend SIUS codes (headcount/data_entries.py SIUS_CODE_VALUES), in the
 * order the planner design lists them. Labels live in i18n/headcount_factor.ts,
 * keyed by the bare code.
 */
export const PLANNER_SIUS_CODES = [
  '51',
  '52',
  '53',
  '54',
  '56',
  '57',
  '58',
  '59',
] as const;

/** The planner's single headcount submodule (a fixed grid, not an add-row table). */
export const PLANNER_HEADCOUNT_SUBMODULE = 'planner_headcount';
