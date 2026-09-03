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
