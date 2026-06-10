<template>
  <div class="chart-empty-state">
    <span class="text-body2 text-secondary">{{ $t('no-chart-data') }}</span>
  </div>
</template>

<style scoped lang="scss">
.chart-empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  min-height: 80px;
  padding: 8px 0;
}
</style>
