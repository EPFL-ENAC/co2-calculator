<script lang="ts" setup>
import { computed } from 'vue';

const props = defineProps<{
  title: string;
  number: string;
  unit?: string;
  comparison?: string;
  comparisonHighlight?: string;
  color?: string;
}>();

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
  <q-card class="container container--pa-none">
    <q-card-section class="flex items-center q-mb-xs">
      <q-icon v-if="$slots.tooltip" name="o_info" size="xs" color="primary">
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

    <q-card-section class="flex no-wrap justify-between items-end">
      <div>
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
        class="text-caption q-mb-none text-right"
        style="width: 50%"
      >
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
