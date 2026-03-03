import { watch } from 'vue';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

/**
 * Composable to handle module-specific chart data fetching
 * Automatically watches for unit/year changes and triggers appropriate fetchers
 */
export function useModuleChartData() {
  const workspaceStore = useWorkspaceStore();
  const moduleStore = useModuleStore();

  // Fetch emission breakdown whenever the carbon report changes.
  // Registered per composable call so watcher lifecycle follows the component.
  watch(
    () => workspaceStore.selectedCarbonReport?.id,
    (carbonReportId) => {
      if (carbonReportId) {
        void moduleStore.getEmissionBreakdown(carbonReportId);
      }
    },
    { immediate: true },
  );

  // Re-fetch emission breakdown after data-entry mutations only.
  // retrieved_at also changes on plain module refreshes, so we gate this
  // with a mutation-driven refresh request from the module store.
  watch(
    () => moduleStore.state.data?.retrieved_at,
    () => {
      if (!moduleStore.consumeEmissionBreakdownRefreshRequest()) return;
      const carbonReportId = workspaceStore.selectedCarbonReport?.id;
      if (!carbonReportId) return;
      moduleStore.invalidateEmissionBreakdown();
      void moduleStore.getEmissionBreakdown(carbonReportId);
    },
  );

  return {
    moduleStore,
  };
}
