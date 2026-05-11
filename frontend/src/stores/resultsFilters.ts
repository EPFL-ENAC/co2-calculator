import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useResultsFiltersStore = defineStore('resultsFilters', () => {
  const hideResearchFacilities = ref(false);
  const hideAdditionalData = ref(false);

  function reset() {
    hideResearchFacilities.value = false;
    hideAdditionalData.value = false;
  }

  return {
    hideResearchFacilities,
    hideAdditionalData,
    reset,
  };
});
