import { useYearConfigStore } from 'src/stores/yearConfig';
import { Module } from 'src/constant/modules';

export function moduleEnabledGuard() {
  return async (to) => {
    // Lighthouse CI bypass
    if (window.__LIGHTHOUSE_BYPASS__) return true;

    const module = to.params.module as Module | undefined;
    if (!module) return true;

    const yearConfigStore = useYearConfigStore();

    // Ensure config is loaded
    if (!yearConfigStore.config) {
      const year = to.params.year as string;
      try {
        await yearConfigStore.fetchConfig(parseInt(year, 10));
      } catch {
        // If config fetch fails, allow access (fallback behavior)
        return true;
      }
    }

    // Check if module is enabled
    if (!yearConfigStore.isModuleVisible(module)) {
      // Module is disabled - redirect to unauthorized
      return {
        name: 'unauthorized',
        params: { language: to.params.language || 'en' },
      };
    }

    return true;
  };
}
