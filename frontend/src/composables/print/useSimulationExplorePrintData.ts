import { computed, ref } from 'vue';
import { useRoute } from 'vue-router';
import { api } from 'src/api/http';
import { getHeadcountMembers } from 'src/api/modules';
import {
  MODULES,
  type Module,
  type Submodule as SubmoduleResponse,
} from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { getExploreModules } from 'src/utils/exploreModules';
import { buildModulePath } from 'src/utils/modulePath';
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

  const exploreModules = computed(() =>
    getExploreModules(yearConfigStore.getModule),
  );

  const submoduleRows = ref<Record<string, PrintRow[]>>({});
  const headcountMembers = ref<Map<string, string>>(new Map());

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

  async function fetchSubmoduleRows(
    moduleType: Module,
    submoduleId: string,
    unitId: number,
    year: number,
  ): Promise<PrintRow[]> {
    const basePath = `${buildModulePath(
      moduleType,
      unitId,
      year,
    )}/${encodeURIComponent(submoduleId)}`;

    const rows: PrintRow[] = [];
    let page = 1;
    for (;;) {
      const queryParams = new URLSearchParams({
        page: String(page),
        limit: '1000',
        carbon_project_type: String(moduleStore.carbonProjectType),
      });
      const response = (await api
        .get(`${basePath}?${queryParams.toString()}`)
        .json()) as SubmoduleResponse;
      rows.push(...(response.items as unknown as PrintRow[]));
      if (
        !response.items.length ||
        rows.length >= response.summary.total_items
      ) {
        break;
      }
      page += 1;
    }
    return rows;
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
        for (const sub of m.submodules) {
          tasks.push(
            fetchSubmoduleRows(m.type, sub.id, unitId, year).then((rows) => {
              submoduleRows.value[sub.id] = rows;
            }),
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
        tasks.push(
          getHeadcountMembers(unitId, year, moduleStore.carbonProjectType).then(
            (members) => {
              headcountMembers.value = new Map(
                members.map((member) => [member.institutional_id, member.name]),
              );
            },
          ),
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
    filteredBreakdown,
    exploreModules,
    submoduleRows,
    headcountMembers,
    initWorkspaceFromRoute,
    fetchAllData,
  };
}
