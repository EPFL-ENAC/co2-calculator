<template>
  <q-card flat class="module-total-result relative container">
    <q-card-section class="module-total-result__container">
      <!-- left side total lab carbon footprint  text i18n-->
      <div class="text-h3">
        {{ $t('module_total_result_title') }}
      </div>
      <!-- right side total lab carbon footprint value  on two lines
           first line:  value in i18n number format 
           second line: kg Co2-eq -->
      <div class="text-h3 module-total-result__value">
        <h4>
          {{ new Intl.NumberFormat().format(data) }}
        </h4>
        <p class="text-body2 text-secondary q-mb-none">
          {{ $t('results_units') }}
        </p>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { Module } from 'src/constant/modules';

defineProps<{
  type: Module;
  data: number;
}>();
</script>
<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-total-result {
  background-color: tokens.$summary-card-bg;
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
