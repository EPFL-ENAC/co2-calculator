import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from 'src/api/http';
import { Router } from 'vue-router';

interface User {
  sciper: string;
  name: string;
  email: string;
  roles: string[];
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

  function login(router?: Router) {
    if (router) {
      router.push('/api/v1/auth/login');
    } else {
      window.location.href = '/api/v1/auth/login';
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
