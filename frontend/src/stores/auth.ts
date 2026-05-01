import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  api,
  API_LOGIN_URL,
  API_LOGOUT_URL,
  API_LOGIN_TEST_URL,
} from 'src/api/http';
import { Router } from 'vue-router';
import { computed } from 'vue';
import { PermissionAction } from 'src/constant/permissions';
import { hasPermission, getModulePermissionPath } from 'src/utils/permission';
import { Module } from 'src/constant/modules';
import { useWorkspaceStore } from './workspace';
interface User {
  id: string;
  email: string;
  display_name?: string;
  is_user_test?: boolean;
  institutional_id?: string;
  roles_raw: Array<{
    role: string;
    on: { unit?: string; affiliation?: string } | 'global';
  }>;
  permissions?: {
    [key: string]: {
      view?: boolean;
      edit?: boolean;
      export?: boolean;
    };
  };
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const loading = ref(false);

  const workspaceStore = useWorkspaceStore();

  const displayName = computed(() => {
    if (!user.value) return '';
    const name =
      user.value.display_name ||
      user.value.email.split('@')[0] ||
      user.value.id ||
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
        const u = await api.get('auth/me').json<User>();
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

  async function logout(router: Router) {
    try {
      loading.value = true;
      await api.post(API_LOGOUT_URL);
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
    console.log(
      `[global] Checking permission for path: ${path} and action: ${action}`,
    );
    if (globallyPermitted) return true;
    // append workspace context to permission path if available
    const institutionalId = workspaceStore.selectedUnit?.institutional_id;
    if (institutionalId) {
      path = `${path}/${institutionalId}`;
      console.log(
        `[workspace] Checking permission for path: ${path} and action: ${action}`,
      );
      return hasPermission(user.value.permissions, path, action);
    }
    console.log(
      `[workspace] No institutional ID found for path: ${path} and action: ${action}`,
    );
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
    if (!path) return false; // FIXME If module doesn't have a permission path, treat as no access
    return hasUserPermission(path, action);
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
    isAuthenticated,
    hasUserPermission,
    hasUserModulePermission,
  };
});
