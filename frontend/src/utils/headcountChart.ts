export function getHeadcountChartKeys(
  stats?: Record<string, number> | null,
): string[] {
  return Object.keys(stats ?? {}).filter(
    (key) => key !== 'student' || (stats?.[key] ?? 0) > 0,
  );
}
