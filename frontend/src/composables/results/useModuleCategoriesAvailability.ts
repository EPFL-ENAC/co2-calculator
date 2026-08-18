import { computed } from 'vue';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { MODULES } from 'src/constant/modules';
import { BUILDING_EMBODIED_ENERGY_SUBMODULE_KEY } from 'src/constant/backoffice-module-config';
import { getModuleForCategoryKey } from 'src/constant/charts';
import { CATEGORY_TO_SUBMODULE } from 'src/composables/useModuleIconColors';

// commuting/food/waste are derived slices of Headcount, embodied_energy of
// Buildings — they aren't real back-office modules, so their activation
// follows their parent module/submodule instead of getModuleForCategoryKey.
// Exported so callers needing the plain category-key list (e.g.
// ModuleCarbonFootprintChart's totals/labels) derive from a single source
// instead of hand-maintaining a second copy that can drift out of sync.
export const ADDITIONAL_HEADCOUNT_CATEGORY_KEYS = ['commuting', 'food', 'waste'];
export const ADDITIONAL_BUILDINGS_CATEGORY_KEYS = ['embodied_energy'];

/**
 * Commuting/food/waste are derived slices of Headcount, and embodied energy
 * (construction & renovation) is a submodule of Buildings — same rule as
 * ModuleCarbonFootprintChart's isModuleActiveForCategory: they only exist
 * once their parent module/submodule is active in the back-office.
 */
export function useModuleCategoriesAvailability() {
  const yearConfigStore = useYearConfigStore();

  const headcountActive = computed(() =>
    yearConfigStore.isModuleVisible(MODULES.Headcount),
  );
  const buildingsActive = computed(() =>
    yearConfigStore.isModuleVisible(MODULES.Buildings),
  );
  const buildingEmbodiedEnergyActive = computed(
    () =>
      yearConfigStore.isModuleVisible(MODULES.Buildings) &&
      yearConfigStore.isSubmoduleVisible(
        MODULES.Buildings,
        BUILDING_EMBODIED_ENERGY_SUBMODULE_KEY,
      ),
  );

  const anyAdditionalCategoryActive = computed(
    () => headcountActive.value || buildingEmbodiedEnergyActive.value,
  );

  // Whether a results category key — main or "additional" — should be shown
  // at all, given back-office module/submodule activation. Mirrors
  // ModuleCarbonFootprintChart's isModuleActiveForCategory: a category also
  // disappears when its owning submodule (e.g. Buildings' energy_combustion)
  // is deactivated, not just its parent module.
  function isCategoryModuleActive(categoryKey: string): boolean {
    if (ADDITIONAL_HEADCOUNT_CATEGORY_KEYS.includes(categoryKey)) {
      return headcountActive.value;
    }
    if (ADDITIONAL_BUILDINGS_CATEGORY_KEYS.includes(categoryKey)) {
      return buildingEmbodiedEnergyActive.value;
    }
    const mod = getModuleForCategoryKey(categoryKey);
    if (!mod) return true;
    if (!yearConfigStore.isModuleVisible(mod)) return false;
    const submodule = CATEGORY_TO_SUBMODULE[categoryKey];
    return submodule
      ? yearConfigStore.isSubmoduleVisible(mod, submodule)
      : true;
  }

  return {
    headcountActive,
    buildingsActive,
    buildingEmbodiedEnergyActive,
    anyAdditionalCategoryActive,
    isCategoryModuleActive,
  };
}
