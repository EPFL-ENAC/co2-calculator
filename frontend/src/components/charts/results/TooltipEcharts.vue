<template>
  <div class="echart-tooltip">
    {{ data }}
    <slot :data="data" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  data: any[];
}>();
</script>

<style>
.echart-tooltip {
  background: #1f1f1f;
  color: white;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  white-space: nowrap;
}
</style>
