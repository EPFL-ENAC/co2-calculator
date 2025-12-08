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
  const loading = ref(false);

  const displayName = computed(() => {
    if (!user.value) return '';
    const name = user.value.email.split('@')[0] || user.value.id || '?';
    return name;
  });

  async function getUser() {
    try {
      loading.value = true;
      user.value = await api.get(`auth/me`).json<User>();
    } catch {
      user.value = null;
    } finally {
      loading.value = false;
    }
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
      user.value = null;
      loading.value = false;
      router.replace({ name: 'login' });
    }
  }

  const isAuthenticated = computed(() => {
    return user.value !== null;
  });

  return {
    user,
    loading,
    displayName,
    getUser,
    login,
    login_test,
    logout,
    isAuthenticated,
  };
});
