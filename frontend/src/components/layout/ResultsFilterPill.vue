<template>
  <Teleport to="body">
    <div class="results-filter-pill non-selectable">
      <div
        class="results-filter-pill__item"
        :class="{
          'results-filter-pill__item--off': store.hideResearchFacilities,
        }"
        @click="store.hideResearchFacilities = !store.hideResearchFacilities"
      >
        <q-icon
          :name="store.hideResearchFacilities ? 'visibility_off' : 'visibility'"
          size="xs"
        />
        <span>{{ $t('charts-research-facilities-category') }}</span>
        <q-icon
          name="o_info"
          size="xs"
          class="results-filter-pill__info"
          @click.stop
        >
          <q-tooltip class="text-body2 text-black">
            {{ $t('results_filter_pill_research_facilities_tooltip') }}
          </q-tooltip>
        </q-icon>
      </div>
      <div class="results-filter-pill__divider" />
      <div
        class="results-filter-pill__item"
        :class="{ 'results-filter-pill__item--off': store.hideAdditionalData }"
        @click="store.hideAdditionalData = !store.hideAdditionalData"
      >
        <q-icon
          :name="store.hideAdditionalData ? 'visibility_off' : 'visibility'"
          size="xs"
        />
        <span>{{ $t('results_additional_data') }}</span>
        <q-icon
          name="o_info"
          size="xs"
          class="results-filter-pill__info"
          @click.stop
        >
          <q-tooltip class="text-body2 text-black">
            {{ $t('results_filter_pill_additional_data_tooltip') }}
          </q-tooltip>
        </q-icon>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useResultsFiltersStore } from 'src/stores/resultsFilters';

const store = useResultsFiltersStore();
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.results-filter-pill {
  position: fixed;
  bottom: tokens.$spacing-xxl;
  right: tokens.$spacing-xxl;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  background: tokens.$color-surface;
  border: 1px solid tokens.$color-border;
  border-radius: tokens.$radius-lg;
  box-shadow: tokens.$shadow-default;
  padding: tokens.$spacing-sm tokens.$spacing-lg;
  gap: tokens.$spacing-sm;
}

.results-filter-pill__item {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-xs;
  cursor: pointer;
  font-size: tokens.$text-size-sm;
  font-weight: tokens.$text-weight-medium;
  color: tokens.$color-text;
  transition:
    color tokens.$transition-default,
    opacity tokens.$transition-default;
}

.results-filter-pill__item--off {
  color: tokens.$color-text-muted;
  opacity: 0.7;
}

.results-filter-pill__divider {
  width: 100%;
  height: tokens.$spacing-xxs;
  background: tokens.$color-border;
}

.results-filter-pill__info {
  margin-left: auto;
  cursor: default;
  color: tokens.$color-text;
}

.results-filter-pill__item--off .results-filter-pill__info {
  color: tokens.$color-text-muted;
}
</style>
