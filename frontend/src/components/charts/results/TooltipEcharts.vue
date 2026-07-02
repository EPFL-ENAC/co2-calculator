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

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.chart-tooltip {
  background: tokens.$tooltip-background;
  color: tokens.$tooltip-color;
  font-size: tokens.$tooltip-fontsize;
  border-radius: tokens.$tooltip-border-radius;
  box-shadow: tokens.$tooltip-box-shadow;
  padding: tokens.$chart-tooltip-padding;
  min-width: tokens.$chart-tooltip-min-width;
  max-width: tokens.$chart-tooltip-max-width;
  width: max-content;

  &__title {
    margin: 0 0 var(--semantic-spacing-xs);
    font-size: var(--semantic-font-size-base);
    font-weight: var(--semantic-font-weight-medium);
  }

  &__row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: nowrap;
    gap: var(--semantic-spacing-sm);
    margin-bottom: 2px;
    font-size: 0.875em;

    &:last-of-type {
      margin-bottom: 0;
    }

    &--separator {
      margin-top: var(--semantic-spacing-xs);
      padding-top: var(--semantic-spacing-xs);
      border-top: 1px solid tokens.$chart-tooltip-separator-color;
      margin-bottom: 0;
    }
  }

  &__label {
    font-size: tokens.$tooltip-fontsize;
    font-weight: var(--semantic-font-weight-medium);
    color: tokens.$tooltip-color;
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  &__dot {
    width: tokens.$chart-tooltip-dot-size;
    height: tokens.$chart-tooltip-dot-size;
    border-radius: 50%;
    background-color: var(--dot-color);
    flex-shrink: 0;
  }

  &__value {
    font-variant-numeric: tabular-nums;
    font-size: tokens.$tooltip-fontsize;
    font-weight: var(--semantic-font-weight-medium);
    color: tokens.$tooltip-color;
    flex: 0 0 auto;
    margin-left: var(--semantic-spacing-sm);
    text-align: right;
    white-space: nowrap;
  }

  &__footer {
    margin: var(--semantic-spacing-xs) 0 0;
    padding-top: var(--semantic-spacing-xs);
    border-top: 1px solid tokens.$chart-tooltip-separator-color;
    font-size: 0.875em;
    font-weight: var(--semantic-font-weight-medium);
    color: tokens.$tooltip-color;

    &--muted {
      color: var(--semantic-color-text-muted);
    }
  }
}
</style>
