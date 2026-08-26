<script setup lang="ts">
/**
 * Calls `listFactors` directly and reports the outcome, so a test can tell a
 * completed slow request apart from an aborted one.
 *
 * The distinction matters: without the per-call timeout override, ky aborts
 * at its 10 s default and this renders `aborted` with a TimeoutError.
 */
import { ref, onMounted } from 'vue';
import { listFactors } from '@/api/factors';
import type { enumSubmodule } from '@/constant/modules';

const props = defineProps<{
  submodule: keyof typeof enumSubmodule;
  year: string;
}>();

const outcome = ref('pending');
const rowCount = ref(-1);
const errorName = ref('');

onMounted(async () => {
  try {
    const rows = await listFactors(props.submodule, props.year);
    rowCount.value = rows.length;
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
  <div data-testid="row-count">{{ rowCount }}</div>
  <div data-testid="error-name">{{ errorName }}</div>
</template>
