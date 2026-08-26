<script setup lang="ts">
/**
 * Fires one request through the shared `api` client directly and reports
 * the outcome, so a test can tell a completed slow request apart from an
 * aborted one.
 *
 * Deliberately calls `api` (`@/api/http`) rather than any specific
 * business API function: the path used here does not need to be a real
 * backend route, since the test mocks the network response entirely. Any
 * endpoint-specific harness this file replaced (`GET factors/{det}/list`,
 * #2391) is exactly the kind of thing that keeps changing — the property
 * under test (does the *client's configured timeout* tolerate a slow
 * response) does not depend on which endpoint happens to be slow.
 */
import { ref, onMounted } from 'vue';
import { api } from '@/api/http';

const outcome = ref('pending');
const errorName = ref('');

onMounted(async () => {
  try {
    await api.get('diagnostics/slow-request-test');
    outcome.value = 'resolved';
  } catch (e: unknown) {
    errorName.value = e instanceof Error ? e.name : String(e);
    outcome.value = 'aborted';
  }
});
</script>

<template>
  <div>harness-ready</div>
  <div data-testid="outcome">{{ outcome }}</div>
  <div data-testid="error-name">{{ errorName }}</div>
</template>
