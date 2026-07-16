<script setup lang="ts">
import { computed, ref } from 'vue';

import BigNumber from 'src/components/molecules/BigNumber.vue';
import ItFocusBreakdownChart from 'src/components/charts/results/ItFocusBreakdownChart.vue';
import { formatTonnesCO2 } from 'src/utils/number';
import type { ItBreakdownResponse } from 'src/stores/modules';

const props = withDefaults(
  defineProps<{
    data: ItBreakdownResponse | null;
    loading?: boolean;
    /** From results summary; used for equivalent car km (kg CO₂-eq / km). */
    co2PerKmKg?: number;
    /** Carbon report year (Results page selected year). */
    year?: number;
    printMode?: boolean;
    compact?: boolean;
  }>(),
  {
    loading: false,
    co2PerKmKg: 0,
    year: undefined,
    printMode: false,
    compact: false,
  },
);

const breakdownChartRef = ref<{ downloadPNG: () => Promise<void> } | null>(
  null,
);

const IT_FOCUS_CATEGORY_ORDER = [
  'equipment_it',
  'external_cloud_and_ai',
  'purchases_it',
  'research_facilities_it',
] as const;

const validatedKeys = computed(
  () => new Set(props.data?.validated_sources ?? []),
);

const displayTotalItTonnes = computed(() => {
  if (!props.data) return 0;
  let sum = 0;
  for (const key of IT_FOCUS_CATEGORY_ORDER) {
    if (validatedKeys.value.has(key)) {
      const cat = props.data.categories.find((c) => c.category_key === key);
      if (cat) sum += cat.tonnes_co2eq;
    }
  }
  return sum;
});

const hasData = computed(() => !!props.data);

const downloadPNG = () => breakdownChartRef.value?.downloadPNG();
</script>

<template>
  <div>
    <template v-if="!printMode">
      <div class="q-pt-lg q-px-lg q-pb-md">
        <h2 class="text-h2 text-weight-medium">
          {{ $t('it-title') }}
        </h2>
        <span class="text-body1 text-secondary">{{
          $t('it-subtitle', { year: year ?? '' })
        }}</span>
      </div>
      <q-separator />
    </template>

    <!-- Summary numbers -->
    <div v-if="data" class="it-stats-row" :class="{ 'q-px-lg': !printMode }">
      <div class="it-stats-row__item">
        <BigNumber
          :title="$t('it-focus-total')"
          :number="`${formatTonnesCO2(displayTotalItTonnes)}`"
          comparison=""
          color="info"
          :bordered="false"
          :print-mode="printMode"
        />
      </div>

      <q-separator vertical />

      <div class="it-stats-row__item">
        <BigNumber
          :title="$t('it-focus-share-of-total')"
          :number="
            data.percentage_of_source_modules != null
              ? `${Math.round(data.percentage_of_source_modules)}%`
              : '-'
          "
          :comparison="$t('it-focus-share-of-total-hint')"
          hide-unit
          color="info"
          :bordered="false"
          :print-mode="printMode"
        />
      </div>
    </div>

    <template v-if="!loading && data">
      <q-separator v-if="!printMode" />

      <q-card v-if="hasData" flat :bordered="printMode" class="q-mb-lg q-px-lg">
        <ItFocusBreakdownChart
          ref="breakdownChartRef"
          :data="data"
          :print-mode="printMode"
          :compact="compact"
        />
      </q-card>

      <template v-if="!printMode">
        <q-separator />
        <q-card-section class="flex justify-start q-gutter-sm">
          <q-btn
            unelevated
            no-caps
            outline
            icon="o_download"
            :label="$t('common_download_as_png')"
            size="xs"
            dense
            class="text-weight-bold q-px-sm"
            @click="downloadPNG"
          />
        </q-card-section>
      </template>
    </template>

    <!-- Loading state -->
    <div v-else-if="loading" class="flex justify-center q-pa-xl">
      <q-spinner color="accent" size="40px" />
    </div>
  </div>
</template>

<style scoped lang="scss">
.it-stats-row {
  display: flex;
  flex-direction: row;
  align-items: stretch;
}

.it-stats-row__item {
  flex: 1;

  :deep(.q-card) {
    border: none !important;
    box-shadow: none !important;
  }
}
</style>
