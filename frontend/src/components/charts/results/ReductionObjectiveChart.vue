<script setup lang="ts">
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import ReductionObjectiveEpflView from 'src/components/charts/results/ReductionObjectiveEpflView.vue';
import ReductionObjectiveUnitView from 'src/components/charts/results/ReductionObjectiveUnitView.vue';

const epflViewRef = ref<{ downloadPNG: () => Promise<void> } | null>(null);
const unitViewRef = ref<{ downloadPNG: () => Promise<void> } | null>(null);

const downloadPNG = () =>
  moduleChartView.value === 'epfl'
    ? epflViewRef.value?.downloadPNG()
    : unitViewRef.value?.downloadPNG();

type ModuleChartView = 'epfl' | 'unit';

interface Props {
  hideResearchFacilities?: boolean;
  hideAdditionalData?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  hideResearchFacilities: false,
  hideAdditionalData: false,
});

const moduleChartView = ref<ModuleChartView>('unit');

const moduleChartViewModel = computed({
  get: () => moduleChartView.value,
  set: (v: ModuleChartView) => {
    moduleChartView.value = v;
  },
});

const { t } = useI18n();

const chartTitle = computed(() =>
  moduleChartView.value === 'epfl'
    ? t('results_objectives_epfl_chart_title')
    : t('results_objectives_unit_chart_title'),
);
</script>
<template>
  <div
    class="row items-start justify-between q-pa-xl q-pb-none q-col-gutter-md"
  >
    <div class="col-12 col-sm">
      <div class="flex items-center no-wrap q-gutter-sm">
        <h2 class="text-h2 text-weight-medium q-mb-none">
          {{ $t('results_objectives_2040_title') }}
        </h2>
        <q-icon name="o_info" size="sm" class="text-primary">
          <q-tooltip class="text-body2 text-black" max-width="320px">
            {{ $t('results_objectives_2030_tooltip') }}
          </q-tooltip>
        </q-icon>
      </div>
      <div class="text-body1 text-secondary">
        {{ $t('results_objectives_2040_section_subtitle') }}
      </div>
    </div>

    <div class="col-12 col-sm-auto flex items-center justify-center">
      <q-btn-toggle
        v-model="moduleChartViewModel"
        dense
        no-caps
        unelevated
        toggle-color="info"
        toggle-text-color="white"
        color="grey-2"
        text-color="grey-7"
        :options="[
          { value: 'unit', slot: 'unit' },
          { value: 'epfl', slot: 'epfl' },
        ]"
        class="chart-view-toggle text-weight-medium"
      >
        <template #unit>
          {{ $t('results_objectives_2040_unit_button') }}
        </template>
        <template #epfl>
          {{ $t('results_objectives_2040_epfl_button') }}
        </template>
      </q-btn-toggle>
    </div>
  </div>

  <q-separator class="q-mb-md" />

  <q-card-section class="q-pa-none">
    <div class="q-pl-xl q-pt-lg">
      <div class="flex items-center no-wrap q-mb-xs">
        <div class="text-body1 text-weight-medium q-mb-none">
          {{ chartTitle }}
        </div>
      </div>

      <div
        v-if="moduleChartView === 'epfl'"
        class="o text-body2 text-secondary"
      >
        {{ $t('results_objectives_2040_subtitle') }}
        (
        <a
          class="link"
          href="https://e4s.center/fr/resources/reports/carbon-removal-net-zero-and-implications-for-switzerland/"
          target="_blank"
          rel="noopener noreferrer"
        >
          {{ $t('results_objectives_2040_subtitle_link_label') }}
        </a>
        )
      </div>

      <div v-else class="text-body2 text-secondary">
        {{ $t('results_objectives_unit_chart_tooltip') }}
      </div>
    </div>

    <q-separator class="q-mt-xl" />

    <div class="q-pl-xl">
      <ReductionObjectiveEpflView
        v-if="moduleChartView === 'epfl'"
        ref="epflViewRef"
        :hide-research-facilities="props.hideResearchFacilities"
      />
      <ReductionObjectiveUnitView
        v-else
        ref="unitViewRef"
        :hide-research-facilities="props.hideResearchFacilities"
        :hide-additional-data="props.hideAdditionalData"
      />
    </div>
  </q-card-section>
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

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.chart-view-toggle {
  :deep(.q-btn) {
    font-weight: tokens.$text-weight-medium;
    font-size: tokens.$text-size-base;
  }
}
</style>
