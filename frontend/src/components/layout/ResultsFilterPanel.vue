<template>
  <!-- Expanded -->
  <div v-if="!collapsed" class="filter-panel non-selectable">
    <span class="filter-panel__title">{{
      $t('results_filter_panel_title')
    }}</span>

    <div
      v-for="row in filters"
      :key="row.key"
      class="filter-panel__row"
      @click="row.toggle()"
    >
      <span
        class="filter-panel__switch"
        :class="{ 'filter-panel__switch--on': !row.hidden }"
        :style="!row.hidden && row.color ? { background: row.color } : {}"
      >
        <span class="filter-panel__switch-thumb" />
      </span>
      <span
        class="filter-panel__label"
        :class="{ 'filter-panel__label--off': row.hidden }"
      >
        {{ row.label }}
      </span>
      <q-icon name="o_info" size="14px" class="filter-panel__info" @click.stop>
        <q-tooltip class="text-body2 text-black">{{ row.tooltip }}</q-tooltip>
      </q-icon>
    </div>
  </div>

  <!-- Collapsed: stacked dot-toggles centered -->
  <div v-else class="filter-panel-mini non-selectable">
    <div
      v-for="row in filters"
      :key="row.key"
      class="filter-panel-mini__dot"
      :class="{ 'filter-panel-mini__dot--off': row.hidden }"
      :style="!row.hidden && row.color ? { background: row.color } : {}"
      @click="row.toggle()"
    >
      <q-tooltip
        anchor="center right"
        self="center left"
        :offset="[6, 0]"
        class="sidebar-tooltip"
      >
        {{ row.label }} -
        {{
          row.hidden
            ? $t('results_filter_hidden')
            : $t('results_filter_visible')
        }}
      </q-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useResultsFiltersStore } from 'src/stores/resultsFilters';
import { CHART_CATEGORY_COLOR_SCHEMES } from 'src/constant/charts';

defineProps<{ collapsed: boolean }>();

const store = useResultsFiltersStore();
const { t } = useI18n();

const filters = computed(() => [
  {
    key: 'research',
    hidden: store.hideResearchFacilities,
    color: CHART_CATEGORY_COLOR_SCHEMES.value.research_facilities,
    label: t('charts-research-facilities-category'),
    tooltip: t('results_filter_pill_research_facilities_tooltip'),
    toggle: () =>
      (store.hideResearchFacilities = !store.hideResearchFacilities),
  },
  {
    key: 'additional',
    hidden: store.hideAdditionalData,
    color: null as string | null,
    label: t('results_additional_data'),
    tooltip: t('results_filter_pill_additional_data_tooltip'),
    toggle: () => (store.hideAdditionalData = !store.hideAdditionalData),
  },
]);
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

// ── Expanded ────────────────────────────────────────────────────────────────

.filter-panel {
  padding: tokens.$spacing-sm tokens.$spacing-md tokens.$spacing-xs;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.filter-panel__title {
  font-size: 10px;
  font-weight: tokens.$text-weight-semibold;
  color: tokens.$color-text-muted;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding-bottom: tokens.$spacing-xs;
}

.filter-panel__row {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-sm;
  padding: 5px tokens.$spacing-xs;
  border-radius: tokens.$radius-default;
  cursor: pointer;
  transition: background-color tokens.$transition-default;

  &:hover {
    background-color: tokens.$color-surface-muted;
  }
}

.filter-panel__switch {
  flex-shrink: 0;
  width: 28px;
  height: 16px;
  border-radius: 8px;
  background: tokens.$color-border;
  position: relative;
  transition: background tokens.$transition-default;

  &--on {
    background: tokens.$color-validated;
  }
}

.filter-panel__switch-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: white;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  transition: transform tokens.$transition-default;

  .filter-panel__switch--on & {
    transform: translateX(12px);
  }
}

.filter-panel__label {
  flex: 1;
  font-size: tokens.$text-size-xs;
  font-weight: tokens.$text-weight-medium;
  color: tokens.$color-text;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color tokens.$transition-default;
  user-select: none;

  &--off {
    color: tokens.$color-text-muted;
  }
}

.filter-panel__info {
  flex-shrink: 0;
  color: tokens.$color-text-muted;
  opacity: 0.6;
}

// ── Collapsed ───────────────────────────────────────────────────────────────

.filter-panel-mini {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: tokens.$spacing-xs;
  padding: tokens.$spacing-sm 0;
}

.filter-panel-mini__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: tokens.$color-validated;
  cursor: pointer;
  transition:
    background tokens.$transition-default,
    opacity tokens.$transition-default,
    transform tokens.$transition-default;

  &:hover {
    transform: scale(1.25);
  }

  &--off {
    background: tokens.$color-border !important;
    opacity: 0.5;
  }
}
</style>
