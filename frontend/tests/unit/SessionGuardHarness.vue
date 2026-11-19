<template>
  <div>
    <div data-testid="result">{{ result }}</div>
    <div data-testid="unavailable">{{ auth.sessionUnavailable }}</div>
    <div data-testid="user">
      {{ auth.user ? `user:${auth.user.id}` : 'none' }}
    </div>
    <button data-testid="guard" @click="runGuard">guard</button>
    <button data-testid="logout" @click="auth.logout(router)">logout</button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { authGuard } from '@/router/guards/authGuard';
import { useAuthStore } from '@/stores/auth';

// Test-only driver for the router guard (#2983): runs the real authGuard on
// a requiresAuth route and renders what it answered, so the spec can assert
// on the guard's verdict, not only on the store.
const auth = useAuthStore();
const router = useRouter();
const empty = { render: () => null };
router.addRoute({ path: '/:language/login', name: 'login', component: empty });
router.addRoute({
  path: '/:language/test',
  name: 'login-test',
  component: empty,
});
router.addRoute({
  path: '/protected',
  name: 'protected',
  meta: { requiresAuth: true },
  component: empty,
});
const result = ref('pending');

async function runGuard() {
  result.value = 'running';
  result.value = JSON.stringify(await authGuard(router.resolve('/protected')));
}
</script>
