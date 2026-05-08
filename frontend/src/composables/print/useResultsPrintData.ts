import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';

import {
  getResultsSummary,
  type ResultsSummary,
  type ModuleResult,
} from 'src/api/modules';
import { MODULES, MODULES_LIST, type Module } from 'src/constant/modules';
import { IT_FOCUS_SOURCE_MODULES } from 'src/constant/itFocus';
import { getModuleTypeId, MODULE_STATES } from 'src/constant/moduleStates';
import { useModuleStore, useTimelineStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

export function useResultsPrintData() {
  const route = useRoute();
  const workspaceStore = useWorkspaceStore();
  const timelineStore = useTimelineStore();
  const moduleStore = useModuleStore();

  const unitParam = computed(() => String(route.params.unit ?? ''));
  const yearParam = computed(() =>
    parseInt(String(route.params.year ?? '0'), 10),
  );

  const resultsSummary = ref<ResultsSummary | null>(null);
  const resultsSummaryLoading = ref(true);

  const currentYear = computed(
    () => yearParam.value || new Date().getFullYear(),
  );

  const hideResearchFacilities = computed(
    () => String(route.query.hideResearchFacilities ?? '0') === '1',
  );
  const hideAdditionalData = computed(
    () => String(route.query.hideAdditionalData ?? '0') === '1',
  );
  const viewAdditionalData = computed(() => !hideAdditionalData.value);

  const excludedModules = computed(() => {
    const ids: number[] = [];
    if (hideResearchFacilities.value) {
      const id = getModuleTypeId(MODULES.ResearchFacilities);
      if (id !== undefined) ids.push(id);
    }
    return ids;
  });

  const co2PerKmKg = computed(() => resultsSummary.value?.co2_per_km_kg ?? 0);
  const hasCo2PerKmKg = computed(() => co2PerKmKg.value > 0);

  const perPersonBreakdown = computed(
    () => moduleStore.state.emissionBreakdown?.per_person_breakdown ?? null,
  );
  const validatedCategories = computed(
    () => moduleStore.state.emissionBreakdown?.validated_categories ?? null,
  );
  const headcountValidatedForPerPerson = computed(
    () => validatedCategories.value?.includes('commuting') ?? false,
  );

  const isModuleValidated = (module: string) =>
    timelineStore.itemStates[module as Module] === MODULE_STATES.Validated;

  const validatedModulesForPrint = computed(() =>
    MODULES_LIST.filter((m) => {
      if (m === MODULES.Headcount) return false;
      if (hideResearchFacilities.value && m === MODULES.ResearchFacilities)
        return false;
      return isModuleValidated(m);
    }),
  );

  const modulesConfig = ref<Record<
    string,
    import('src/constant/moduleConfig').ModuleConfig
  > | null>(null);

  const loadModulesConfig = async () => {
    if (!modulesConfig.value) {
      const { MODULES_CONFIG } = await import('src/constant/module-config');
      modulesConfig.value = MODULES_CONFIG;
    }
  };

  const getModuleConfig = (module: string) => modulesConfig.value?.[module];

  const getModuleResult = (module: string): ModuleResult | undefined => {
    if (!resultsSummary.value) return undefined;
    const typeId = getModuleTypeId(module as Module);
    return resultsSummary.value.module_results.find(
      (m) => m.module_type_id === typeId,
    );
  };

  const additionalBreakdown = computed(
    () => moduleStore.state.emissionBreakdown?.additional_breakdown ?? [],
  );
  const commutingRow = computed(
    () =>
      additionalBreakdown.value.find((r) => r.category_key === 'commuting') ??
      null,
  );
  const foodRow = computed(
    () =>
      additionalBreakdown.value.find((r) => r.category_key === 'food') ?? null,
  );
  const wasteRow = computed(
    () =>
      additionalBreakdown.value.find((r) => r.category_key === 'waste') ?? null,
  );
  const embodiedEnergyRow = computed(
    () =>
      additionalBreakdown.value.find(
        (r) => r.category_key === 'embodied_energy',
      ) ?? null,
  );
  const embodiedEnergyByCategory = computed(
    () =>
      moduleStore.state.emissionBreakdown?.embodied_energy_by_category ?? [],
  );

  const validatedAdditionalTonnes = computed(() => {
    const validated = new Set(
      moduleStore.state.emissionBreakdown?.validated_categories ?? [],
    );
    return additionalBreakdown.value.reduce((sum, row) => {
      if (!validated.has(row.category_key)) return sum;
      const catTotal = row.emissions.reduce((categorySum, emission) => {
        return (
          categorySum +
          (typeof emission.value === 'number' ? emission.value : 0)
        );
      }, 0);
      return sum + catTotal;
    }, 0);
  });

  const adjustedTotalTonnes = computed(() => {
    const raw = resultsSummary.value?.unit_totals.total_tonnes_co2eq;
    if (raw == null) return null;
    return viewAdditionalData.value
      ? raw
      : raw - validatedAdditionalTonnes.value;
  });

  const adjustedTonnesPerFte = computed(() => {
    const fte = resultsSummary.value?.unit_totals.total_fte;
    if (adjustedTotalTonnes.value == null || !fte || fte <= 0) return null;
    return adjustedTotalTonnes.value / fte;
  });

  const additionalChartsValidated = computed(() => {
    const breakdown = moduleStore.state.emissionBreakdown;
    if (!breakdown) return false;
    return breakdown.headcount_validated || breakdown.buildings_validated;
  });

  const showItFocusSection = computed(() =>
    IT_FOCUS_SOURCE_MODULES.some(
      (m) => timelineStore.itemStates[m] === MODULE_STATES.Validated,
    ),
  );

  const modulePagesStart = 2;
  const itPageNumber = computed(
    () => modulePagesStart + validatedModulesForPrint.value.length,
  );
  const additionalPageNumber = computed(
    () => itPageNumber.value + (showItFocusSection.value ? 1 : 0),
  );

  async function initWorkspaceFromRoute() {
    workspaceStore.setSelectedParams({
      unit: unitParam.value,
      year: yearParam.value,
    });

    await workspaceStore.getUnits();

    const routeUnit = String(workspaceStore.selectedParams?.unit || '');
    const unitIdFromRoute = routeUnit.split('-')[0];
    const validUnit = workspaceStore.units.find(
      (unit) =>
        unit.id === parseInt(unitIdFromRoute, 10) || unit.name === routeUnit,
    );

    if (!validUnit) {
      workspaceStore.setUnit(null);
      workspaceStore.setYear(null);
      return null;
    }

    workspaceStore.setUnit(validUnit);
    workspaceStore.setYear(workspaceStore.selectedParams?.year || null);

    await workspaceStore.selectCarbonReportForYear(
      workspaceStore.selectedUnit.id,
      workspaceStore.selectedYear,
    );

    const carbonReportId = workspaceStore.selectedCarbonReport?.id ?? null;
    if (carbonReportId) {
      await timelineStore.fetchModuleStates(carbonReportId);
    }

    return carbonReportId;
  }

  async function fetchAllData(carbonReportId: number) {
    try {
      resultsSummaryLoading.value = true;
      resultsSummary.value = await getResultsSummary(
        carbonReportId,
        excludedModules.value,
      );
    } catch {
      resultsSummary.value = null;
    } finally {
      resultsSummaryLoading.value = false;
    }

    await moduleStore.getEmissionBreakdown(
      carbonReportId,
      excludedModules.value,
    );
    await moduleStore.getItBreakdown(carbonReportId, excludedModules.value);
  }

  return {
    resultsSummary,
    resultsSummaryLoading,
    currentYear,
    viewAdditionalData,
    co2PerKmKg,
    hasCo2PerKmKg,
    perPersonBreakdown,
    validatedCategories,
    headcountValidatedForPerPerson,
    validatedModulesForPrint,
    getModuleResult,
    getModuleConfig,
    additionalBreakdown,
    commutingRow,
    foodRow,
    wasteRow,
    embodiedEnergyRow,
    embodiedEnergyByCategory,
    adjustedTotalTonnes,
    adjustedTonnesPerFte,
    additionalChartsValidated,
    showItFocusSection,
    modulePagesStart,
    itPageNumber,
    additionalPageNumber,
    initWorkspaceFromRoute,
    fetchAllData,
    loadModulesConfig,
  };
}
