<template>
  <q-card flat class="container">
    <q-card-section class="text-center module-charts">
      <h2 class="text-h3 q-mb-none text-bold text-uppercase">
        {{ $t(`${props.type}-charts-title`) }}
      </h2>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
const props = defineProps<{
  type: string;
}>();
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-charts {
  padding: tokens.$graph-card-padding; // Example padding, adjust as needed
  color: tokens.$graph-color-primary; // Use your token for secondary text
  font-weight: tokens.$graph-font-weight;
  font-size: tokens.$graph-font-size;
  line-height: tokens.$graph-line-height;
}
</style>
