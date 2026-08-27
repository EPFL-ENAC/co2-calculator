<script setup lang="ts">
/**
 * Calls `getDataEntryTaxonomy` directly and reports the outcome, so a test
 * can tell a completed slow request apart from an aborted one.
 *
 * The distinction matters: without the client-wide timeout override, ky
 * aborts at its 10 s default and this renders `aborted` with a TimeoutError.
 * `getDataEntryTaxonomy` is the #2391-era replacement for the `listFactors`
 * call this harness used to exercise — `factors/{det}/list` no longer
 * exists on either side.
 */
import { ref, onMounted } from 'vue';
import { getDataEntryTaxonomy } from '@/api/taxonomies';

const props = defineProps<{
  moduleType: string;
  dataEntry: string;
  year: string;
}>();

const outcome = ref('pending');
const childCount = ref(-1);
const errorName = ref('');

onMounted(async () => {
  try {
    const node = await getDataEntryTaxonomy(
      props.moduleType,
      props.dataEntry,
      props.year,
    );
    childCount.value = node.children?.length ?? 0;
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
  <div data-testid="child-count">{{ childCount }}</div>
  <div data-testid="error-name">{{ errorName }}</div>
</template>
