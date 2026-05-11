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
          size="16px"
        />
        <span>{{ $t('charts-research-facilities-category') }}</span>
        <q-icon
          name="o_info"
          size="14px"
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
          size="16px"
        />
        <span>{{ $t('results_additional_data') }}</span>
        <q-icon
          name="o_info"
          size="14px"
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

<style scoped>
.results-filter-pill {
  position: fixed;
  bottom: 32px;
  right: 32px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  padding: 8px 16px;
  gap: 8px;
}

.results-filter-pill__item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: #212121;
  transition:
    color 0.2s ease,
    opacity 0.2s ease;
}

.results-filter-pill__item--off {
  color: #9e9e9e;
  opacity: 0.7;
}

.results-filter-pill__divider {
  width: 100%;
  height: 1px;
  background: #e0e0e0;
}

.results-filter-pill__info {
  margin-left: auto;
  cursor: default;
  color: #212121;
}

.results-filter-pill__item--off .results-filter-pill__info {
  color: #9e9e9e;
}
</style>
