<template>
  <q-card flat class="container" style="padding: 0">
    <q-card-section class="text-left module-charts">
      <template v-if="type === 'my-lab'">
        <h2 class="text-h5 text-weight-medium q-mb-none text-bold text-black">
          {{ $t('my-lab-charts-title') }}
        </h2>
        <headCountBarChart :stats="moduleStore?.state?.data?.stats" />
      </template>
      <h2 v-else class="text-h3 q-mb-none text-bold text-uppercase">
        {{ $t(`${type}-charts-title`) }}
      </h2>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { Module } from 'src/constant/modules';
import HeadCountBarChart from 'src/components/molecules/HeadCountBarChart.vue';
import { useModuleStore } from 'src/stores/modules';

defineProps<{
  type: Module;
}>();

const moduleStore = useModuleStore();
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-charts {
  // padding: tokens.$graph-card-padding; // Example padding, adjust as needed
  color: tokens.$graph-color-primary; // Use your token for secondary text
  font-weight: tokens.$graph-font-weight;
  font-size: tokens.$graph-font-size;
  line-height: tokens.$graph-line-height;
}
</style>
