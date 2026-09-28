<template>
  <div data-testid="result">{{ result }}</div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useAuthStore } from '@/stores/auth';

// Test-only driver for the session bootstrap (#2943): runs the real store
// against an intercepted GET /session and renders the outcome, so the spec
// can assert on text while counting requests.
const result = ref('pending');

onMounted(async () => {
  try {
    const user = await useAuthStore().bootstrap();
    result.value = user ? `user:${user.id}` : 'anonymous';
  } catch (e: unknown) {
    result.value = `error:${e instanceof Error ? e.message : String(e)}`;
  }
});
</script>
