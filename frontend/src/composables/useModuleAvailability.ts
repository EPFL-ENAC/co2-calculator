import { useAuthStore } from '@/stores/auth';
import { useYearConfigStore } from '@/stores/yearConfig';
import type { Module } from '@/constant/modules';

/**
 * Whether a module renders normally (clickable) or greyed-out on Home's
 * chart icon axis. Only two signals decide this: the module is enabled in
 * the backoffice year config, and the current user has view or edit access
 * to it. Module status (not started / in progress / validated) and data
 * presence never grey an icon — a module the user can access renders
 * normally even before it has any computed stats.
 */
export function isModuleFullyAvailable(module: Module | null): boolean {
  if (!module) return false;
  const yearConfigStore = useYearConfigStore();
  const authStore = useAuthStore();
  return (
    yearConfigStore.isModuleVisible(module) &&
    authStore.canUserAccessModule(module)
  );
}
