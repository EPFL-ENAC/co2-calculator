import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from 'src/api/http';
import { Router } from 'vue-router';
import { useWorkspaceStore } from './workspace';

interface User {
  id: string;
  sciper: number;
  email: string;
  roles: Array<{
    role: string;
    on: { unit?: string; affiliation?: string } | 'global';
  }>;
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const loading = ref(true);

  async function fetchUser() {
    try {
      loading.value = true;
      const fetchedUser = await api.get('auth/me').json<User>();
      user.value = fetchedUser;
    } catch (error) {
      user.value = null;
      console.error('Error fetching user:', error);
    } finally {
      loading.value = false;
    }
  }

  async function login(router?: Router) {
    try {
      const fetchedUser = await api.get('auth/login').json<User>();
      user.value = fetchedUser;

      const workspaceStore = useWorkspaceStore();
      const language = router
        ? (router.currentRoute.value.params.language as string) || 'en'
        : 'en';

      if (workspaceStore.selectedUnit && workspaceStore.selectedYear) {
        const unitName = encodeURIComponent(workspaceStore.selectedUnit.name);
        const year = workspaceStore.selectedYear;
        if (router) {
          router.push({
            name: 'home',
            params: { language, unit: unitName, year },
          });
        } else {
          window.location.href = `/${language}/${unitName}/${year}/home`;
        }
      } else {
        if (router) {
          router.push({ name: 'workspace-setup', params: { language } });
        } else {
          window.location.href = `/${language}/workspace-setup`;
        }
      }
    } catch (error) {
      console.error('Error logging in:', error);
    }
  }

  async function logout(router?: Router) {
    try {
      await api.post('auth/logout');
    } catch (error) {
      console.error('Error logging out:', error);
    } finally {
      user.value = null;
      loading.value = false;
      const language = router
        ? (router.currentRoute.value.params.language as string) || 'en'
        : 'en';
      if (router) {
        router.push({ name: 'login', params: { language } });
      } else {
        window.location.href = `/${language}/login`;
      }
    }
  }

  return {
    user,
    loading,
    fetchUser,
    login,
    logout,
  };
});
