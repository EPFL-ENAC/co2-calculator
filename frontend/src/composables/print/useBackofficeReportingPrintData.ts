import { computed } from 'vue';
import { useBackofficePrintBase } from './useBackofficePrintBase';
import { MODULE_STATES } from 'src/constant/moduleStates';
import type { ReportingStats } from 'src/api/backoffice';

export function useBackofficeReportingPrintData() {
  const base = useBackofficePrintBase();
  const { units } = base;

  const tableRows = computed(() => units.value?.data ?? []);

  const usageStats = computed<ReportingStats>(() => ({
    [MODULE_STATES.Default]: units.value?.not_started_units_count ?? 0,
    [MODULE_STATES.InProgress]: units.value?.in_progress_units_count ?? 0,
    [MODULE_STATES.Validated]: units.value?.validated_units_count ?? 0,
  }));

  const moduleStats = computed<ReportingStats>(() => {
    const counts = units.value?.module_status_counts ?? {};
    return {
      [MODULE_STATES.Default]: counts[0] ?? 0,
      [MODULE_STATES.InProgress]: counts[1] ?? 0,
      [MODULE_STATES.Validated]: counts[2] ?? 0,
    };
  });

  const totalModules = computed(() => {
    const counts = units.value?.module_status_counts ?? {};
    return Object.values(counts).reduce((a, b) => a + b, 0);
  });

  return {
    ...base,
    tableRows,
    usageStats,
    moduleStats,
    totalModules,
  };
}
