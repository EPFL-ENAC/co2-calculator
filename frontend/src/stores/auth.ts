import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  api,
  API_EXCHANGE_URL,
  API_LOGIN_URL,
  API_LOGOUT_URL,
  API_LOGIN_TEST_URL,
  API_ME_URL,
} from 'src/api/http';
import { Router } from 'vue-router';
import { computed } from 'vue';
import {
  PermissionAction,
  type FlatUserPermissions,
} from 'src/constant/permissions';
import {
  hasPermission,
  hasAnyScopePermission,
  hasBackOfficeAreaPermission,
  getModulePermissionPath,
} from 'src/utils/permission';
import { Module } from 'src/constant/modules';
import type { components } from 'src/types/api/openapi';
import { useWorkspaceStore } from './workspace';

// `UserRead` comes from the FastAPI OpenAPI schema (issue #217 POC).
// `permissions` and `roles_raw` are intentionally widened in the backend
// schema (`additionalProperties: true`, computed fields), so we keep their
// runtime-accurate narrowing locally instead of casting at every call site.
type GeneratedUserRead = components['schemas']['UserRead'];
type User = Omit<
  GeneratedUserRead,
  'permissions' | 'roles_raw' | 'institutional_id'
> & {
  permissions?: FlatUserPermissions;
  // `roles_raw` is normalized to `[]` at the API boundary in `getUser()`, so
  // callers can safely `.map()` without an optional guard.
  roles_raw: Array<{
    role: string;
    on: { unit?: string; affiliation?: string } | 'global';
  }>;
  // Backend uses `response_model_exclude_none=True`, which strips
  // `institutional_id` from the wire when null even though the generated
  // type marks it required. Reflect runtime reality locally.
  institutional_id?: string;
};

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const loading = ref(false);

  const workspaceStore = useWorkspaceStore();

  const displayName = computed(() => {
    if (!user.value) return '';
    const name =
      user.value.display_name ||
      user.value.email.split('@')[0] ||
      String(user.value.id) ||
      '?';
    return name;
  });

  const hasChecked = ref(false);
  let inflight: Promise<User | null> | null = null;

  async function getUser(): Promise<User | null> {
    if (inflight) return inflight;

    inflight = (async () => {
      try {
        loading.value = true;
        const raw = await api.get(API_ME_URL).json<User>();
        // Backend serializes roles as `[]` or omits the field under
        // `response_model_exclude_none=True`. Normalize once here so
        // every call site can treat `roles_raw` as a non-optional array.
        const u: User = { ...raw, roles_raw: raw.roles_raw ?? [] };
        user.value = u;
        return u;
      } catch {
        user.value = null;
        return null;
      } finally {
        loading.value = false;
        hasChecked.value = true;
        inflight = null;
      }
    })();

    return inflight;
  }

  function login_test(role: string) {
    window.location.replace(`${API_LOGIN_TEST_URL}?role=${role}`);
  }

  function login() {
    window.location.replace(API_LOGIN_URL);
  }

  /**
   * Trade the single-use OAuth-callback code for session cookies (BFF
   * leg 2; ADR-019). Run from the /auth/complete landing page after the
   * IdP redirect lands there with a `#code=<...>` fragment.
   */
  async function exchange(code: string): Promise<User | null> {
    await api
      .post(API_EXCHANGE_URL, { json: { code }, retry: { limit: 0 } })
      .json<{ id: number; email: string }>();
    // The backend already wrote the cookies; hydrate the full user
    // profile (roles, permissions, display_name) via /session.
    return await getUser();
  }

  async function logout(router: Router) {
    try {
      loading.value = true;
      await api.delete(API_LOGOUT_URL);
    } catch (error) {
      console.error('Error logging out:', error);
    } finally {
      // Check server-issued is_user_test flag to determine routing.
      if (user.value?.is_user_test) {
        // For test users, just go to home login-test page
        user.value = null;
        loading.value = false;
        router.replace({ name: 'login-test' });
      } else {
        user.value = null;
        loading.value = false;
        router.replace({ name: 'login' });
      }
    }
  }

  const isAuthenticated = computed(() => {
    return user.value !== null;
  });

  /**
   * Check if current user has a specific permission.
   *
   * @param path The permission path to check (e.g., 'modules.headcount')
   * @param action The action to check (e.g., 'view')
   * @returns boolean indicating if the user has the specified permission
   */
  function hasUserPermission(
    path: string,
    action: PermissionAction = PermissionAction.VIEW,
  ): boolean {
    if (!user.value || !user.value.permissions) return false;
    // Check for global permission first (without workspace context)
    const globallyPermitted = hasPermission(
      user.value.permissions,
      path,
      action,
    );
    if (globallyPermitted) return true;
    // append workspace context to permission path if available
    const institutionalId = workspaceStore.selectedUnit?.institutional_id;
    if (institutionalId) {
      path = `${path}/${institutionalId}`;
      return hasPermission(user.value.permissions, path, action);
    }
    return false;
  }

  /**
   * Check if current user has a specific permission for a module.
   * This is a convenience function that derives the permission path from the module.
   *
   * @param module The module to check permissions for
   * @param action The action to check (e.g., 'view')
   * @returns boolean indicating if the user has the specified permission for the module
   */
  function hasUserModulePermission(
    module: Module,
    action: PermissionAction = PermissionAction.VIEW,
  ): boolean {
    const path = getModulePermissionPath(module);
    if (!path) return false; // If module doesn't have a permission path, treat as no access
    return hasUserPermission(path, action);
  }

  function canUserAccessModule(module: Module): boolean {
    const path = getModulePermissionPath(module);
    if (!path) return true; // Unprotected module, accessible to all users
    return (
      hasUserAnyScopePermission(path, PermissionAction.VIEW) ||
      hasUserAnyScopePermission(path, PermissionAction.EDIT)
    );
  }

  /**
   * Check if the current user can access the back-office area (any
   * `backoffice.*` or `system.*` permission granting `action`). Use for
   * generic entry points (e.g. the header button) that should appear for
   * any back-office user regardless of role, sub-domain, or affiliation.
   */
  function hasUserBackOfficeAreaPermission(
    action: PermissionAction = PermissionAction.VIEW,
  ): boolean {
    if (!user.value || !user.value.permissions) return false;
    return hasBackOfficeAreaPermission(user.value.permissions, action);
  }

  /**
   * Check if the current user has `action` on `path` under ANY scope
   * (bare path OR any `path/<*>` variant). Use for back-office route
   * guards and menu gates that should accept GlobalScope, unit-scoped,
   * and affiliation-scoped users alike.
   */
  function hasUserAnyScopePermission(
    path: string,
    action: PermissionAction = PermissionAction.VIEW,
  ): boolean {
    if (!user.value || !user.value.permissions) return false;
    return hasAnyScopePermission(user.value.permissions, path, action);
  }

  return {
    user,
    loading,
    hasChecked,
    displayName,
    getUser,
    login,
    login_test,
    logout,
    exchange,
    isAuthenticated,
    hasUserPermission,
    hasUserModulePermission,
    canUserAccessModule,
    hasUserBackOfficeAreaPermission,
    hasUserAnyScopePermission,
  };
});
