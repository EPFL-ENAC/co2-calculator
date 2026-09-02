/**
 * The 8 backend SIUS codes (headcount/data_entries.py SIUS_CODE_VALUES), in the
 * order the planner design lists them. Labels are backend-served (#2613):
 * the planner_headcount taxonomy vocabulary, or each row's `labels`.
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

/**
 * Students have no SIUS code: they are their own grid row, prefilled from the
 * reference year's student submodule and priced with the student factors.
 */
export const PLANNER_STUDENT_CODE = 'student';

export const PLANNER_HEADCOUNT_CODES = [
  ...PLANNER_SIUS_CODES,
  PLANNER_STUDENT_CODE,
] as const;

/**
 * SIUS labels come from the backend (#2613); the students row is a UI
 * construct and keeps its own i18n key. `label` is whatever backend label
 * the caller holds (row `labels`, taxonomy vocabulary) — the bare code is
 * the English-side fallback while nothing is loaded yet.
 */
export function plannerHeadcountRowLabel(
  code: string,
  label: string | null | undefined,
  t: (key: string) => string,
): string {
  if (code === PLANNER_STUDENT_CODE) {
    return t('planner_headcount_student_category');
  }
  return label ?? code;
}
