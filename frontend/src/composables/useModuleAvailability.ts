import { useAuthStore } from '@/stores/auth';
import { useYearConfigStore } from '@/stores/yearConfig';
import { PermissionAction } from '@/utils/permission';
import type { Module } from '@/constant/modules';

/**
 * Single source of truth for "does this module render normally, or
 * greyed-out" — shared across every page that shows module-level results
 * (Home's chart icon axis, Results' per-module list, the backoffice
 * Reporting aggregate). A module renders normally only when it's enabled
 * in the backoffice AND the current user has EDIT permission on it AND it
 * actually has computed stats; otherwise it's shown greyed out (visible,
 * non-interactive) rather than hidden — a module should never silently
 * disappear or reappear differently depending on which page you're on.
 */
export function isModuleFullyAvailable(
  module: Module | null,
  hasStats: boolean,
): boolean {
  if (!module) return false;
  const yearConfigStore = useYearConfigStore();
  const authStore = useAuthStore();
  return (
    hasStats &&
    yearConfigStore.isModuleVisible(module) &&
    authStore.hasUserModulePermission(module, PermissionAction.EDIT)
  );
}
