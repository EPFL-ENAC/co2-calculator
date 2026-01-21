import { watch, type Ref } from 'vue';
import { Module, MODULES } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

type ChartDataFetcher = (unitId: number, year: string) => Promise<void> | void;

/**
 * Configuration map for module-specific chart data fetching
 * Add new modules here by mapping their type to a fetch function
 */
const moduleChartFetchers: Partial<Record<Module, ChartDataFetcher>> = {
  [MODULES.ProfessionalTravel]: (unitId: number, year: string) => {
    const moduleStore = useModuleStore();
    return moduleStore.getTravelStatsByClass(unitId, year);
  },
  // Add more modules here as needed:
  // [MODULES.Infrastructure]: (unitId: string, year: string) => {
  //   const moduleStore = useModuleStore();
  //   return moduleStore.getInfrastructureStats(unitId, year);
  // },
};

/**
 * Composable to handle module-specific chart data fetching
 * Automatically watches for unit/year changes and triggers appropriate fetchers
 */
export function useModuleChartData(moduleType: Ref<Module>) {
  const workspaceStore = useWorkspaceStore();
  const moduleStore = useModuleStore();

  const fetchChartData = (unitId: number | undefined, year: number | null) => {
    if (!unitId || !year) return;

    const fetcher = moduleChartFetchers[moduleType.value];
    if (fetcher) {
      fetcher(unitId, String(year));
    }
  };

  // Watch for unit/year changes and fetch chart data when available
  watch(
    [() => workspaceStore.selectedUnit?.id, () => workspaceStore.selectedYear],
    ([unitId, year]) => {
      fetchChartData(unitId, year);
    },
    { immediate: true },
  );

  return {
    moduleStore,
  };
}
