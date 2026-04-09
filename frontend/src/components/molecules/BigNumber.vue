<script lang="ts" setup>
import { computed } from 'vue';

const props = defineProps<{
  title: string;
  number: string;
  unit?: string;
  comparison?: string;
  comparisonHighlight?: string;
  color?: string;
  tooltipPlacement?: 'title' | 'comparison';
}>();

const tooltipPlacement = computed(() => props.tooltipPlacement ?? 'title');

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
  <q-card flat class="container container--pa-none full-width big-number">
    <q-card-section class="flex items-center q-mb-xs">
      <q-icon
        v-if="$slots.tooltip && tooltipPlacement === 'title'"
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
        <div class="text-secondary text-body2 q-mb-none">
          {{ unit ? unit : $t('results_units_tonnes') }}
        </div>
      </div>

      <div
        v-if="comparisonParts.length > 0"
        class="text-caption q-mb-none text-right big-number__comparison"
        style="width: 50%"
      >
        <q-icon
          v-if="$slots.tooltip && tooltipPlacement === 'comparison'"
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
  align-self: flex-start;
  white-space: normal;
  overflow-wrap: anywhere;
}
</style>
