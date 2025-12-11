<template>
  <q-card flat class="module-total-result relative container">
    <q-card-section class="module-total-result__container items-center">
      <!-- left side total lab carbon footprint  text i18n-->
      <div class="text-body1 text-weight-medium">
        {{ $t('module_total_result_title', { type: $t(type) }) }}
      </div>
      <!-- right side total lab carbon footprint value  on two lines
           first line:  value in i18n number format 
           second line: kg CO₂-eq -->
      <div class="text-h3 module-total-result__value">
        <h1 class="text-h1 text-weight-bold q-mb-none">
          {{ formatNumber(data) }}
        </h1>
        <p class="text-body2 text-secondary q-mb-none">
          {{ $t('results_units') }}
        </p>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { Module } from 'src/constant/modules';
import { formatNumber } from 'src/utils/number';

defineProps<{
  type: Module;
  data: number;
}>();
</script>
<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-total-result {
  background-color: tokens.$module-result-bg;
  border: tokens.$module-result-border-weight solid
    tokens.$module-result-border-color;
  border-radius: tokens.$module-result-border-radius;
  padding: tokens.$module-result-padding-y tokens.$module-result-padding-x;
}
.module-total-result__container {
  display: grid;
  grid-auto-flow: column;
  justify-content: space-between;
}
.module-total-result__value {
  text-align: right;
  display: grid;
  grid-auto-flow: row;
}
</style>
