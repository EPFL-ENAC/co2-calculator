import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { getHeadcountMembers } from 'src/api/modules';
import { MODULES } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { sumBreakdownTonnes } from 'src/utils/breakdownTotal';
import { getExploreModules } from 'src/utils/exploreModules';
import {
  fetchPlannerHeadcountRows,
  type PlannerHeadcountRow,
} from 'src/utils/plannerHeadcountRows';
import { fetchAllSubmoduleRows } from 'src/utils/printSubmoduleRows';
import type { PrintRow } from 'src/utils/printTable';

export function useSimulationExplorePrintData() {
  const route = useRoute();
  const workspaceStore = useWorkspaceStore();
  const moduleStore = useModuleStore();
  const yearConfigStore = useYearConfigStore();

  const unitParam = computed(() => String(route.params.unit ?? ''));
  const yearParam = computed(() =>
    parseInt(String(route.params.year ?? '0'), 10),
  );
  const currentYear = computed(
    () => yearParam.value || new Date().getFullYear(),
  );

  const loading = ref(true);

  const totalTonnesCo2eq = computed(() =>
    sumBreakdownTonnes(moduleStore.state.emissionBreakdown),
  );

  const breakdown = computed(() => moduleStore.state.emissionBreakdown);

  const exploreModules = computed(() =>
    getExploreModules(yearConfigStore.getModule),
  );

  const submoduleRows = ref<Record<string, PrintRow[]>>({});
  const headcountMembers = ref<Map<string, string>>(new Map());
  const plannerHeadcountRows = ref<PlannerHeadcountRow[]>([]);

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

    await yearConfigStore.fetchConfig(yearParam.value);

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
      const unitId = workspaceStore.selectedUnit?.id;
      const year = workspaceStore.selectedYear;
      if (unitId == null || year == null) return;

      const tasks: Promise<unknown>[] = [
        moduleStore.getEmissionBreakdown(carbonReportId, []),
      ];

      for (const m of exploreModules.value) {
        // Headcount is the Planner's fixed SIUS-category grid (#2070), not
        // the Calculator submodule tables.
        if (m.type === MODULES.Headcount) {
          tasks.push(
            fetchPlannerHeadcountRows(carbonReportId)
              .then((rows) => {
                plannerHeadcountRows.value = rows;
              })
              .catch(() => {
                plannerHeadcountRows.value = [];
              }),
          );
          continue;
        }
        for (const sub of m.submodules) {
          tasks.push(
            fetchAllSubmoduleRows(m.type, sub.id, carbonReportId).then(
              (rows) => {
                submoduleRows.value[sub.id] = rows;
              },
            ),
          );
          if (sub.moduleFields.some((f) => f.optionsId === 'kind')) {
            tasks.push(
              moduleStore.getSubmoduleTaxonomy(m.type, sub.id, String(year)),
            );
          }
        }
      }

      if (
        exploreModules.value.some((m) => m.type === MODULES.ProfessionalTravel)
      ) {
        const carbonReportId = await moduleStore.resolveCarbonReportId(
          unitId,
          year,
        );
        tasks.push(
          getHeadcountMembers(carbonReportId).then((members) => {
            headcountMembers.value = new Map(
              members.map((member) => [member.institutional_id, member.name]),
            );
          }),
        );
      }

      await Promise.all(tasks);
    } finally {
      loading.value = false;
    }
  }

  return {
    currentYear,
    loading,
    totalTonnesCo2eq,
    breakdown,
    exploreModules,
    submoduleRows,
    headcountMembers,
    plannerHeadcountRows,
    initWorkspaceFromRoute,
    fetchAllData,
  };
}
