/**
 * Bars for the "FTE by function" chart from the module's persisted stats
 * (#2706): member FTE keyed by SIUS code plus the "student" sentinel. Null
 * member groups (a group with no FTE recorded) draw no bar.
 */
export function headcountChartStats(
  stats?: Record<string, unknown> | null,
): Record<string, number> {
  const members = stats?.member_fte_by_sius_code;
  const result: Record<string, number> = {};
  if (members && typeof members === 'object') {
    for (const [code, fte] of Object.entries(members)) {
      if (typeof fte === 'number') result[code] = fte;
    }
  }
  const student = stats?.student_fte;
  if (typeof student === 'number') result.student = student;
  return result;
}

export function getHeadcountChartKeys(
  stats?: Record<string, number> | null,
): string[] {
  return Object.keys(stats ?? {}).filter(
    (key) => key !== 'student' || (stats?.[key] ?? 0) > 0,
  );
}

/**
 * `stats` keys are raw SIUS codes (`"51"`, `"-1"`, ...) plus the "student"
 * sentinel (headcount/data_entries.py) — never a vue-i18n key. Resolve each
 * through the member taxonomy vocabulary (#2613, same source ModuleTable and
 * ModuleForm use), falling back to the bare code while the vocabulary hasn't
 * loaded yet rather than showing nothing.
 */
export function resolveHeadcountCategoryLabel(
  key: string,
  suisLabels: Record<string, string>,
  studentLabel: string,
): string {
  if (key === 'student') return studentLabel;
  return suisLabels[key] ?? key;
}
