<template>
  <div v-if="tooltipState" class="chart-tooltip">
    <p v-if="tooltipState.title" class="chart-tooltip__title">
      {{ tooltipState.title }}
    </p>

    <div
      v-for="(row, i) in tooltipState.rows"
      :key="i"
      class="chart-tooltip__row"
    >
      <ModuleIcon
        v-if="row.icon"
        :name="row.icon"
        size="sm"
        color=""
        :style="{ color: row.color ?? 'currentColor' }"
      />
      <span
        v-else-if="row.color"
        class="chart-tooltip__dot"
        :style="{ '--dot-color': row.color }"
      />
      <span class="chart-tooltip__label">{{ row.label }}</span>
      <span class="chart-tooltip__value">{{ row.value }}</span>
    </div>

    <div
      v-if="tooltipState.separatorRow"
      class="chart-tooltip__row chart-tooltip__row--separator row items-center"
    >
      <span
        v-if="tooltipState.separatorRow.color"
        class="chart-tooltip__dot"
        :style="{ '--dot-color': tooltipState.separatorRow.color }"
      />
      <span class="chart-tooltip__label col">{{
        tooltipState.separatorRow.label
      }}</span>
      <span class="chart-tooltip__value text-weight-medium">{{
        tooltipState.separatorRow.value
      }}</span>
    </div>

    <p
      v-if="tooltipState.footer"
      class="chart-tooltip__footer"
      :class="{ 'chart-tooltip__footer--muted': tooltipState.tone === 'muted' }"
    >
      {{ tooltipState.footer }}
    </p>
  </div>
</template>

<script setup lang="ts">
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import type { TooltipState } from 'src/types/chartTooltip';

defineProps<{
  tooltipState: TooltipState;
}>();
</script>
