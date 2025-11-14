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

      const destination =
        workspaceStore.selectedUnit && workspaceStore.selectedYear
          ? `/${workspaceStore.selectedUnit.id}/${workspaceStore.selectedYear}/home`
          : '/workspace-setup';

      if (router) {
        router.push(destination);
      } else {
        window.location.href = destination;
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
      if (router) {
        router.push('/login');
      } else {
        window.location.href = '/login';
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
