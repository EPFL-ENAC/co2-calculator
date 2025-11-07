import { defineStore } from 'pinia';
import { api } from 'src/api/http';
import { Router } from 'vue-router';

interface User {
  sciper: string;
  name: string;
  email: string;
  roles: string[];
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as User | null,
    loading: true,
  }),
  actions: {
    async fetchUser() {
      try {
        this.loading = true;
        const user = await api.get('auth/me').json<User>();
        this.user = user;
      } catch (error) {
        this.user = null;
        console.error('Error fetching user:', error);
      } finally {
        this.loading = false;
      }
    },
    login() {
      window.location.href = '/api/v1/auth/login';
    },
    async logout(router?: Router) {
      try {
        await api.post('auth/logout');
      } catch (error) {
        console.error('Error logging out:', error);
      } finally {
        this.user = null;
        this.loading = false;
        // Use provided router or fallback
        if (router) {
          router.push('/login');
        } else {
          window.location.href = '/login';
        }
      }
    },
  },
});
