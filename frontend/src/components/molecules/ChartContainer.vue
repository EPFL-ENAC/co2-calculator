<script setup lang="ts">
defineProps<{
  title: string;
}>();
</script>
<template>
  <q-card flat class="container container--pa-none">
    <q-card-section class="flex items-center">
      <q-icon name="o_info" size="xs" color="primary">
        <q-tooltip
          v-if="$slots.tooltip"
          anchor="center right"
          self="top right"
          class="u-tooltip"
        >
          <slot name="tooltip"></slot>
        </q-tooltip>
      </q-icon>
      <span class="text-body1 text-weight-medium q-ml-sm q-mb-none">
        {{ title }}
      </span>
    </q-card-section>
    <q-card-section class="chart-container">
      <slot />
    </q-card-section>
  </q-card>
</template>
<style scoped lang="scss">
.chart-container {
  padding: 16px;
  padding: 24px;
  margin: 0;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
