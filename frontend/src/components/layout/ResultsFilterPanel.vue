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
      @click="row.toggle"
    >
      <span
        class="filter-panel__switch"
        :class="{ 'filter-panel__switch--on': !row.hidden }"
        :style="filterAccentStyle(row)"
      >
        <span class="filter-panel__switch-thumb" />
      </span>
      <span
        class="filter-panel__label"
        :class="{ 'filter-panel__label--off': row.hidden }"
      >
        {{ row.label }}
      </span>
      <q-icon
        :name="outlinedInfo"
        size="14px"
        class="filter-panel__info"
        @click.stop
      >
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
      :style="filterAccentStyle(row)"
      @click="row.toggle"
    >
      <ModuleIcon
        :name="row.iconName"
        color=""
        size="md"
        class="filter-panel-mini__icon"
      />
      <span class="filter-panel-mini__circle" />
      <q-tooltip
        anchor="center right"
        self="center left"
        :offset="[6, 0]"
        class="sidebar-tooltip"
      >
        {{ row.label }} - {{ visibilityLabel(row.hidden) }}
      </q-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';
import { useResultsFiltersStore } from 'src/stores/resultsFilters';
import { CHART_CATEGORY_COLOR_SCHEMES } from 'src/constant/charts';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

defineProps<{ collapsed: boolean }>();

const store = useResultsFiltersStore();
const { t } = useI18n();

function visibilityLabel(hidden: boolean): string {
  return hidden ? t('results_filter_hidden') : t('results_filter_visible');
}

function filterAccentStyle(row: { hidden: boolean; color: string | null }) {
  if (!row.hidden && row.color) {
    return { '--filter-accent-color': row.color };
  }
  return {};
}

const filters = computed(() => [
  {
    key: 'research',
    hidden: store.hideResearchFacilities,
    color: CHART_CATEGORY_COLOR_SCHEMES.value.research_facilities,
    iconName: 'research-facilities',
    label: t('charts-research-facilities-category'),
    tooltip: t('results_filter_pill_research_facilities_tooltip'),
    toggle: () =>
      (store.hideResearchFacilities = !store.hideResearchFacilities),
  },
  {
    key: 'additional',
    hidden: store.hideAdditionalData,
    color: null as string | null,
    iconName: 'addition-datas',
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
  padding: tokens.$spacing-lg tokens.$spacing-md;
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
  transition: background-color tokens.$transition-default;
}

.filter-panel__switch {
  flex-shrink: 0;
  width: 28px;
  height: 16px;
  border-radius: 8px;
  background: tokens.$color-border;
  position: relative;
  cursor: pointer;
  transition: background tokens.$transition-default;

  &--on {
    background: var(--filter-accent-color, #{tokens.$color-validated});
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
  gap: tokens.$spacing-md;
  padding: tokens.$spacing-sm 0 tokens.$spacing-lg;
}

.filter-panel-mini__dot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1px;
  cursor: pointer;
  transition:
    opacity tokens.$transition-default,
    transform tokens.$transition-default;

  &:hover {
    transform: scale(1.15);
  }

  &--off {
    opacity: 0.5;
  }
}

.filter-panel-mini__icon {
  color: var(--filter-accent-color, #{tokens.$color-validated});
  flex-shrink: 0;
}

.filter-panel-mini__circle {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--filter-accent-color, #{tokens.$color-validated});
  flex-shrink: 0;

  .filter-panel-mini__dot--off & {
    background: tokens.$color-border;
  }
}
</style>
