<script lang="ts" setup>
import { computed } from 'vue';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';

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
    colorStyle?: string;
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
    colorStyle: undefined,
    tooltipPlacement: 'title',
    printMode: false,
  },
);

const { t } = useI18n();

const tooltipPlacement = computed(() => props.tooltipPlacement);

const displayUnit = computed(() => props.unit ?? t('results_units_tonnes'));

const valueClass = computed(() => (props.color ? `text-${props.color}` : ''));

const valueStyle = computed(() =>
  props.colorStyle ? { color: props.colorStyle } : {},
);

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
      { 'big-number--borderless': !bordered },
      { 'big-number--print': printMode },
    ]"
  >
    <q-card-section class="flex items-center q-mb-xs">
      <span
        class="text-body1 text-weight-medium q-mb-none"
        :class="{
          'q-mr-sm': $slots.tooltip && tooltipPlacement === 'title',
        }"
      >
        {{ title }}
      </span>
      <q-icon
        v-if="$slots.tooltip && tooltipPlacement === 'title' && !printMode"
        :name="outlinedInfo"
        size="xs"
        color="primary"
      >
        <q-tooltip anchor="center right" self="top right" class="u-tooltip">
          <slot name="tooltip"></slot>
        </q-tooltip>
      </q-icon>
    </q-card-section>

    <q-card-section class="flex no-wrap justify-between big-number__content">
      <div class="big-number__value">
        <div
          class="text-h1 text-weight-medium q-mb-none"
          :class="valueClass"
          :style="valueStyle"
        >
          {{ number }}
        </div>
        <div v-if="!hideUnit" class="text-secondary text-body2 q-mb-none">
          {{ displayUnit }}
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
          :name="outlinedInfo"
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
@use 'src/css/02-tokens' as tokens;

.big-number {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.big-number--borderless {
  border: none !important;
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
    outline: 1px solid tokens.$print-outline-color !important;
    border-radius: tokens.$radius-default !important;
  }
}

.big-number--print {
  :deep(.q-card-section) {
    padding: tokens.$spacing-sm tokens.$spacing-md tokens.$spacing-xs;
  }

  .big-number__value :deep(.text-h1) {
    font-size: tokens.$print-big-number-font-size !important;
    line-height: 1.2 !important;
  }

  .text-body1 {
    font-size: tokens.$print-title-font-size !important;
    line-height: 1.2 !important;
  }

  .text-body2 {
    font-size: tokens.$print-unit-font-size !important;
  }

  .text-caption {
    font-size: tokens.$print-caption-font-size !important;
  }
}
</style>
