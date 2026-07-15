import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from 'src/api/http';
import { useModuleStore } from 'src/stores/modules';

/**
 * Hand-typed DTOs mirroring backend/app/schemas/simulator_plan.py; re-run
 * `cd frontend && make gen-api-types` against an up-to-date backend to
 * replace with generated `paths['/project-plans/...']` types.
 */
export interface SimulatorPlan {
  id: number;
  unit_id: number;
  name: string;
  start_year: number | null;
  end_year: number | null;
  is_viewable_by_unit_members: boolean;
  created_by: number | null;
  created_at: string | null;
  creator_name: string | null;
}

export interface SimulatorPlanModule {
  id: number;
  carbon_report_id: number;
  module_type_id: number;
  status: number;
  is_active: boolean;
  stats: Record<string, unknown> | null;
}

/** One plan-year carbon report with its modules. */
export interface SimulatorPlanYear {
  id: number;
  year: number;
  reference_year: number | null;
  stats: Record<string, unknown> | null;
  modules: SimulatorPlanModule[];
}

export interface SimulatorPlanUpdatePayload {
  name?: string;
  start_year?: number;
  end_year?: number;
  is_viewable_by_unit_members?: boolean;
}

export const useSimulatorPlansStore = defineStore('simulatorPlans', () => {
  const plans = ref<SimulatorPlan[]>([]);
  const loading = ref(false);

  // Per-year reports of the currently open plan (Project Planner page).
  const planYears = ref<SimulatorPlanYear[]>([]);
  const planYearsLoading = ref(false);

  /**
   * Registers the plan-year report ids with the module store so
   * identity-addressed module calls resolve year → carbon_report_id
   * (a unit can hold many plans, unit/year lookup cannot apply).
   */
  function registerPlannerReports(years: SimulatorPlanYear[]) {
    const moduleStore = useModuleStore();
    moduleStore.setPlannerReportIds(
      Object.fromEntries(years.map((y) => [y.year, y.id])),
    );
  }

  async function fetchPlans(unitId: number): Promise<void> {
    loading.value = true;
    try {
      plans.value = await api
        .get(`project-plans/unit/${unitId}/`)
        .json<SimulatorPlan[]>();
    } finally {
      loading.value = false;
    }
  }

  async function createPlan(
    unitId: number,
    name?: string,
  ): Promise<SimulatorPlan> {
    return api
      .post(`project-plans/unit/${unitId}/`, {
        json: { name: name ?? null },
      })
      .json<SimulatorPlan>();
  }

  async function getPlanByName(
    unitId: number,
    name: string,
  ): Promise<SimulatorPlan> {
    return api
      .get(`project-plans/unit/${unitId}/by-name/${encodeURIComponent(name)}`, {
        skipErrorCodes: [404],
      })
      .json<SimulatorPlan>();
  }

  /**
   * PATCH the plan (name / year range / lab visibility). Changing the year
   * range syncs the plan's per-year reports server-side, so the years list
   * is refetched afterwards.
   */
  async function updatePlan(
    planId: number,
    payload: SimulatorPlanUpdatePayload,
  ): Promise<SimulatorPlan> {
    const plan = await api
      .patch(`project-plans/${planId}`, { json: payload })
      .json<SimulatorPlan>();
    if (payload.start_year !== undefined || payload.end_year !== undefined) {
      await fetchPlanYears(planId);
    }
    return plan;
  }

  async function renamePlan(
    planId: number,
    name: string,
  ): Promise<SimulatorPlan> {
    return updatePlan(planId, { name });
  }

  async function fetchPlanYears(planId: number): Promise<SimulatorPlanYear[]> {
    planYearsLoading.value = true;
    try {
      planYears.value = await api
        .get(`project-plans/${planId}/years`)
        .json<SimulatorPlanYear[]>();
      registerPlannerReports(planYears.value);
      return planYears.value;
    } finally {
      planYearsLoading.value = false;
    }
  }

  /** Set the reference (baseline) year of one plan-year report. */
  async function setReferenceYear(
    planId: number,
    year: number,
    referenceYear: number,
  ): Promise<SimulatorPlanYear> {
    const updated = await api
      .patch(`project-plans/${planId}/years/${year}`, {
        json: { reference_year: referenceYear },
      })
      .json<SimulatorPlanYear>();
    planYears.value = planYears.value.map((y) =>
      y.year === updated.year ? updated : y,
    );
    return updated;
  }

  /** Toggle a module's Active checkbox on one plan-year report. */
  async function setModuleActive(
    carbonReportId: number,
    moduleTypeId: number,
    isActive: boolean,
  ): Promise<SimulatorPlanModule> {
    const updated = await api
      .patch(
        `carbon-reports/${carbonReportId}/modules/${moduleTypeId}/active`,
        { json: { is_active: isActive } },
      )
      .json<SimulatorPlanModule>();
    planYears.value = planYears.value.map((y) =>
      y.id === carbonReportId
        ? {
            ...y,
            modules: y.modules.map((m) =>
              m.module_type_id === moduleTypeId ? updated : m,
            ),
          }
        : y,
    );
    return updated;
  }

  async function duplicatePlan(planId: number): Promise<SimulatorPlan> {
    return api.post(`project-plans/${planId}/duplicate`).json<SimulatorPlan>();
  }

  async function deletePlan(planId: number): Promise<void> {
    await api.delete(`project-plans/${planId}`);
  }

  return {
    plans,
    loading,
    planYears,
    planYearsLoading,
    fetchPlans,
    createPlan,
    getPlanByName,
    updatePlan,
    renamePlan,
    fetchPlanYears,
    setReferenceYear,
    setModuleActive,
    duplicatePlan,
    deletePlan,
  };
});
