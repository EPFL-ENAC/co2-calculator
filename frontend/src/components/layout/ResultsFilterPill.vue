<template>
  <Teleport to="body">
    <div class="results-filter-pill non-selectable">
      <div
        class="results-filter-pill__item"
        :class="{
          'results-filter-pill__item--hidden': store.hideResearchFacilities,
          'results-filter-pill__item--shown': !store.hideResearchFacilities,
        }"
        @click="store.hideResearchFacilities = !store.hideResearchFacilities"
      >
        <q-icon :name="researchFacilitiesIcon" size="xs" />
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
        :class="{
          'results-filter-pill__item--hidden': store.hideAdditionalData,
          'results-filter-pill__item--shown': !store.hideAdditionalData,
        }"
        @click="store.hideAdditionalData = !store.hideAdditionalData"
      >
        <q-icon :name="additionalDataIcon" size="xs" />
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
import { computed } from 'vue';
import { useResultsFiltersStore } from 'src/stores/resultsFilters';

const store = useResultsFiltersStore();

const researchFacilitiesIcon = computed(() =>
  store.hideResearchFacilities ? 'visibility_off' : 'visibility',
);
const additionalDataIcon = computed(() =>
  store.hideAdditionalData ? 'visibility_off' : 'visibility',
);
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.results-filter-pill {
  position: fixed;
  bottom: calc(tokens.$spacing-lg + env(safe-area-inset-bottom));
  right: calc(tokens.$spacing-lg + env(safe-area-inset-right));
  z-index: tokens.$z-index-floating;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  background: tokens.$color-surface;
  border: 1px solid tokens.$color-border;
  border-radius: tokens.$radius-default;

  padding: tokens.$spacing-xs tokens.$spacing-md;
  gap: tokens.$spacing-xs;
}

@media (max-width: tokens.$breakpoint-mobile-max) {
  .results-filter-pill {
    left: 50%;
    right: auto;
    transform: translateX(-50%);
    max-width: calc(100vw - (tokens.$spacing-md * 2));
  }
}

.results-filter-pill__item {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-xs;
  cursor: pointer;
  font-size: tokens.$text-size-xs;
  font-weight: tokens.$text-weight-medium;
  color: tokens.$color-text;
  transition:
    color tokens.$transition-default,
    opacity tokens.$transition-default;
}

.results-filter-pill__item--shown {
  color: tokens.$color-text;
}

.results-filter-pill__item--shown :deep(.q-icon) {
  color: tokens.$color-text;
}

.results-filter-pill__item--hidden {
  color: tokens.$color-text-muted;
  opacity: tokens.$opacity-muted;
}

.results-filter-pill__item--hidden :deep(.q-icon) {
  color: tokens.$color-text-muted;
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

.results-filter-pill__item--hidden .results-filter-pill__info {
  color: tokens.$color-text-muted;
}
</style>
