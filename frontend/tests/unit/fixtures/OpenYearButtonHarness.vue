<script setup lang="ts">
/**
 * Seeds the year-config store with a backend-shaped response, then renders
 * OpenYearButton against it — the store is what the button reads.
 */
import { useYearConfigStore } from '@/stores/yearConfig';
import type { YearConfigurationResponse } from '@/stores/yearConfig';
import OpenYearButton from '@/components/molecules/data-management/OpenYearButton.vue';

const props = defineProps<{ response: YearConfigurationResponse }>();

useYearConfigStore().setConfig(props.response);
</script>

<template>
  <open-year-button :year="props.response.year" />
</template>
