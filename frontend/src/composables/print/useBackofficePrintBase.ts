import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useBackofficeStore } from 'src/stores/backoffice';
import type { UnitFilters } from 'src/stores/backoffice';
import { MODULES } from 'src/constant/modules';
import { MODULE_TO_CATEGORIES } from 'src/constant/charts';

const BREAKDOWN_MODULES = [
  MODULES.ProcessEmissions,
  MODULES.Buildings,
  MODULES.Equipment,
  MODULES.ExternalCloudAndAI,
  MODULES.Purchase,
  MODULES.ResearchFacilities,
  MODULES.ProfessionalTravel,
] as const;

export function useBackofficePrintBase() {
  const route = useRoute();
  const backofficeStore = useBackofficeStore();

  const filters = computed<UnitFilters>(() => {
    const raw = String(route.query.filters ?? '{}');
    try {
      return JSON.parse(raw) as UnitFilters;
    } catch {
      return {};
    }
  });

  const units = computed(() => backofficeStore.units);
  const loading = computed(() => backofficeStore.unitsLoading);
  const reportingEmissionBreakdown = computed(
    () => units.value?.emission_breakdown ?? null,
  );
  const reportingItBreakdown = computed(
    () => units.value?.it_breakdown ?? null,
  );
  const validatedCount = computed(
    () => units.value?.validated_units_count ?? 0,
  );
  const tableTotal = computed(() => units.value?.total_units_count ?? 0);

  const availableModules = computed(() => {
    if (!reportingEmissionBreakdown.value) return [];
    const rows = reportingEmissionBreakdown.value.module_breakdown;
    return BREAKDOWN_MODULES.filter((mod) => {
      const categories = MODULE_TO_CATEGORIES.value[mod] ?? [];
      return categories.some((cat) => {
        const row = rows.find(
          (r) => r['category'] === cat || r['category_key'] === cat,
        );
        if (!row) return false;
        return Object.entries(row).some(
          ([k, v]) =>
            k !== 'category' &&
            k !== 'category_key' &&
            !k.endsWith('StdDev') &&
            Number(v) > 0,
        );
      });
    });
  });

  async function fetchData() {
    backofficeStore.unitsPagination.pageSize = 5000;
    await backofficeStore.getUnits(filters.value);
  }

  return {
    filters,
    units,
    loading,
    reportingEmissionBreakdown,
    reportingItBreakdown,
    validatedCount,
    tableTotal,
    availableModules,
    fetchData,
  };
}
