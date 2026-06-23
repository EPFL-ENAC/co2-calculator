import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';

export function useSimulationExplorePrintData() {
  const route = useRoute();
  const workspaceStore = useWorkspaceStore();
  const moduleStore = useModuleStore();

  const unitParam = computed(() => String(route.params.unit ?? ''));
  const yearParam = computed(() =>
    parseInt(String(route.params.year ?? '0'), 10),
  );
  const currentYear = computed(
    () => yearParam.value || new Date().getFullYear(),
  );

  const loading = ref(true);

  const totalTonnesCo2eq = computed(() => {
    const breakdown = moduleStore.state.emissionBreakdown;
    if (!breakdown) return 0;
    const moduleTotal = (breakdown.module_breakdown ?? []).reduce(
      (sum, row) => {
        const rowTotal = (row.emissions ?? []).reduce((rowSum, e) => {
          return rowSum + (typeof e.value === 'number' ? e.value : 0);
        }, 0);
        return sum + rowTotal;
      },
      0,
    );
    return moduleTotal || breakdown.total_tonnes_co2eq || 0;
  });

  const filteredBreakdown = computed(() => {
    const bd = moduleStore.state.emissionBreakdown;
    if (!bd) return bd;
    return {
      ...bd,
      module_breakdown: bd.module_breakdown.filter(
        (entry) => entry.category !== 'research_facilities',
      ),
    };
  });

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

    const carbonReport =
      await workspaceStore.selectSimulatorExploreCarbonReport(
        workspaceStore.selectedUnit.id,
        workspaceStore.selectedYear,
      );

    return carbonReport?.id ?? null;
  }

  async function fetchAllData(carbonReportId: number) {
    try {
      loading.value = true;
      await moduleStore.getEmissionBreakdown(carbonReportId, []);
    } finally {
      loading.value = false;
    }
  }

  return {
    currentYear,
    loading,
    totalTonnesCo2eq,
    filteredBreakdown,
    initWorkspaceFromRoute,
    fetchAllData,
  };
}
