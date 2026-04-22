<script lang="ts" setup>
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    title: string;
    number: string;
    unit?: string;
    hideUnit?: boolean;
    bordered?: boolean;
    comparison?: string;
    comparisonHighlight?: string;
    color?: string;
    tooltipPlacement?: 'title' | 'comparison';
    printMode?: boolean;
  }>(),
  {
    bordered: true,
    unit: undefined,
    hideUnit: false,
    comparison: undefined,
    comparisonHighlight: undefined,
    color: undefined,
    tooltipPlacement: 'title',
    printMode: false,
  },
);

const tooltipPlacement = computed(() => props.tooltipPlacement);

const comparisonParts = computed(() => {
  if (!props.comparison) {
    return [];
  }

  if (!props.comparisonHighlight) {
    return [{ text: props.comparison, bold: false }];
  }

  const index = props.comparison.indexOf(props.comparisonHighlight);
  if (index === -1) {
    return [{ text: props.comparison, bold: false }];
  }

  const before = props.comparison.substring(0, index);
  const highlight = props.comparisonHighlight;
  const after = props.comparison.substring(index + highlight.length);

  return [
    { text: before, bold: false },
    { text: highlight, bold: true },
    { text: after, bold: false },
  ];
});
</script>

<template>
  <q-card
    flat
    :bordered="bordered"
    :class="[
      'container',
      'container--pa-none',
      'big-number',
      { 'big-number--print': printMode },
    ]"
  >
    <q-card-section class="flex items-center q-mb-xs">
      <q-icon
        v-if="$slots.tooltip && tooltipPlacement === 'title' && !printMode"
        name="o_info"
        size="xs"
        color="primary"
      >
        <q-tooltip anchor="center right" self="top right" class="u-tooltip">
          <slot name="tooltip"></slot>
        </q-tooltip>
      </q-icon>
      <span
        class="text-body1 text-weight-medium q-mb-none"
        :class="{
          'q-ml-sm': $slots.tooltip && tooltipPlacement === 'title',
        }"
      >
        {{ title }}
      </span>
    </q-card-section>

    <q-card-section class="flex no-wrap justify-between big-number__content">
      <div class="big-number__value">
        <div
          class="text-h1 text-weight-medium q-mb-none"
          :class="color ? `text-${color}` : ''"
        >
          {{ number }}
        </div>
        <div v-if="!hideUnit" class="text-secondary text-body2 q-mb-none">
          {{ unit ? unit : $t('results_units_tonnes') }}
        </div>
      </div>

      <div
        v-if="comparisonParts.length > 0"
        class="text-caption q-mb-none text-right big-number__comparison"
        style="width: 50%"
      >
        <q-icon
          v-if="
            $slots.tooltip && tooltipPlacement === 'comparison' && !printMode
          "
          name="o_info"
          size="xs"
          color="primary"
          class="q-mr-xs"
        >
          <q-tooltip anchor="center right" self="top right" class="u-tooltip">
            <slot name="tooltip"></slot>
          </q-tooltip>
        </q-icon>
        <span
          v-for="(part, index) in comparisonParts"
          :key="index"
          :class="{ 'text-weight-bold': part.bold }"
        >
          {{ part.text }}
        </span>
      </div>
    </q-card-section>
  </q-card>
</template>

<style scoped lang="scss">
.big-number {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.big-number__content {
  margin-top: auto;
  align-items: flex-end;
}

.big-number__value {
  align-self: flex-end;
}

.big-number__comparison {
  align-self: flex-end;
  white-space: normal;
  overflow-wrap: anywhere;
}

@media print {
  .big-number.q-card--bordered {
    outline: 1px solid rgba(0, 0, 0, 0.2) !important;
    border-radius: 4px !important;
  }
}

.big-number--print {
  :deep(.q-card-section) {
    padding: 8px 10px 4px;
  }

  .big-number__value :deep(.text-h1) {
    font-size: 1.4rem !important;
    line-height: 1.2 !important;
  }

  .text-body1 {
    font-size: 0.75rem !important;
    line-height: 1.2 !important;
  }

  .text-body2 {
    font-size: 0.7rem !important;
  }

  .text-caption {
    font-size: 0.65rem !important;
  }
}
</style>
