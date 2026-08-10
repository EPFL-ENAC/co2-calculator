import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from 'src/api/http';
import type { ReportStats } from 'src/utils/emissionStatsAdapter';

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
  /** Latest Calculator report year of the unit; factor fallback when a plan
   * year has no reference year (backend-derived, read-only). */
  default_factor_year: number | null;
  is_grant_proposal: boolean;
  created_by: number | null;
  created_at: string | null;
  creator_name: string | null;
  total_tonnes_co2eq: number | null;
  can_manage: boolean;
}

export interface SimulatorPlanModule {
  id: number;
  carbon_report_id: number;
  module_type_id: number;
  status: number;
  is_active: boolean;
  /** Grant submodule budgets, keyed by submodule id (#1978). */
  budgets: Record<string, number> | null;
  stats: Record<string, unknown> | null;
}

/**
 * One plan carbon report with its modules: a year of the range, or the
 * Project Grant report (`is_grant`, anchored to the start year).
 */
export interface SimulatorPlanYear {
  id: number;
  year: number;
  reference_year: number | null;
  is_grant: boolean;
  budget: number | null;
  budget_currency: string | null;
  stats: Record<string, unknown> | null;
  modules: SimulatorPlanModule[];
}

export interface SimulatorPlanUpdatePayload {
  name?: string;
  start_year?: number;
  end_year?: number;
  is_viewable_by_unit_members?: boolean;
  /** Reference year defaulted onto (and prefilled into) year reports newly
   * created by this range change; send the current workspace year. */
  default_reference_year?: number;
  is_grant_proposal?: boolean;
  /** Not persisted: opts the plan out of (or back into) per-year sections. */
  with_year_sections?: boolean;
}

export const useSimulatorPlansStore = defineStore('simulatorPlans', () => {
  const plans = ref<SimulatorPlan[]>([]);
  const loading = ref(false);

  // Per-year reports of the currently open plan (Project Planner page).
  const planYears = ref<SimulatorPlanYear[]>([]);
  const planYearsLoading = ref(false);

  // Whole-plan stats aggregate behind the planner results card. `activePlanId`
  // is set while the Project Planner page is mounted and drives
  // `refreshAggregateIfActive`, the hook the module store calls after entry
  // mutations.
  const activePlanId = ref<number | null>(null);
  const aggregateStats = ref<ReportStats | null>(null);
  // The Project Grant report's own stats — charted beside the year
  // aggregate, never summed into it (#1977).
  const grantStats = ref<ReportStats | null>(null);
  const aggregateLoading = ref(false);

  const plansStale = ref(false);

  async function fetchPlans(unitId: number): Promise<void> {
    loading.value = true;
    try {
      plans.value = await api
        .get(`project-plans/unit/${unitId}/`)
        .json<SimulatorPlan[]>();
      plansStale.value = false;
    } finally {
      loading.value = false;
    }
  }

  function setPlans(rows: SimulatorPlan[]): void {
    plans.value = rows;
    plansStale.value = false;
  }

  function markPlansStale(): void {
    plansStale.value = true;
  }

  async function createPlan(
    unitId: number,
    name?: string,
  ): Promise<SimulatorPlan> {
    const plan = await api
      .post(`project-plans/unit/${unitId}/`, {
        json: { name: name ?? null },
      })
      .json<SimulatorPlan>();

    markPlansStale();
    return plan;
  }

  async function getPlan(planId: number): Promise<SimulatorPlan> {
    return api
      .get(`project-plans/${planId}`, {
        skipErrorCodes: [404],
      })
      .json<SimulatorPlan>();
  }

  /**
   * PATCH the plan (name / year range / lab visibility). Changing the year
   * range, grant flag or year-sections flag syncs the plan's reports
   * server-side, so the years list and the results aggregate are refetched
   * afterwards.
   */
  async function updatePlan(
    planId: number,
    payload: SimulatorPlanUpdatePayload,
  ): Promise<SimulatorPlan> {
    const rangeChange =
      payload.start_year !== undefined || payload.end_year !== undefined;
    const plan = await api
      .patch(`project-plans/${planId}`, {
        json: payload,
        // A range change prefills every new year report from the default
        // reference year, same workload as setReferenceYear below.
        ...(rangeChange ? { timeout: 300000 } : {}),
      })
      .json<SimulatorPlan>();

    markPlansStale();
    if (
      rangeChange ||
      payload.is_grant_proposal !== undefined ||
      payload.with_year_sections !== undefined
    ) {
      await fetchPlanYears(planId);
      await refreshAggregateIfActive();
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
      return planYears.value;
    } finally {
      planYearsLoading.value = false;
    }
  }

  async function fetchAggregateStats(planId: number): Promise<void> {
    activePlanId.value = planId;
    aggregateLoading.value = true;
    try {
      const payload = await api
        .get(`project-plans/${planId}/aggregate-stats`)
        .json<{ years: ReportStats; grant: ReportStats | null }>();
      aggregateStats.value = payload.years;
      grantStats.value = payload.grant;
    } finally {
      aggregateLoading.value = false;
    }
  }

  async function refreshAggregateIfActive(): Promise<void> {
    if (activePlanId.value === null) return;
    markPlansStale();
    await fetchAggregateStats(activePlanId.value);
  }

  function clearAggregate(): void {
    activePlanId.value = null;
    aggregateStats.value = null;
    grantStats.value = null;
  }

  /**
   * Set or remove (null) the reference (baseline) year of one plan-year report. `isGrant`
   * targets the Project Grant report, which shares its year with the
   * start-year report.
   */
  async function setReferenceYear(
    planId: number,
    year: number,
    referenceYear: number | null,
    isGrant = false,
  ): Promise<SimulatorPlanYear> {
    const updated = await api
      .patch(`project-plans/${planId}/years/${year}`, {
        json: { reference_year: referenceYear, is_grant: isGrant },
        timeout: 300000, // 5 minutes; TODO: backend to make a background task instead!
      })
      .json<SimulatorPlanYear>();
    planYears.value = planYears.value.map((y) =>
      y.id === updated.id ? updated : y,
    );
    await refreshAggregateIfActive();
    return updated;
  }

  /** Replace one module inside its plan-year, immutably, in local state. */
  function replaceModuleInYear(
    carbonReportId: number,
    updated: SimulatorPlanModule,
  ) {
    planYears.value = planYears.value.map((y) =>
      y.id === carbonReportId
        ? {
            ...y,
            modules: y.modules.map((m) =>
              m.module_type_id === updated.module_type_id ? updated : m,
            ),
          }
        : y,
    );
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
    replaceModuleInYear(carbonReportId, updated);
    await refreshAggregateIfActive();
    return updated;
  }

  /** Set the Project Grant report's total budget and its currency (#1978). */
  async function setGrantBudget(
    carbonReportId: number,
    budget: number | null,
    budgetCurrency: string | null,
  ): Promise<void> {
    const updated = await api
      .patch(`carbon-reports/${carbonReportId}/budget`, {
        json: { budget, budget_currency: budgetCurrency },
      })
      .json<{ budget: number | null; budget_currency: string | null }>();
    planYears.value = planYears.value.map((y) =>
      y.id === carbonReportId
        ? {
            ...y,
            budget: updated.budget,
            budget_currency: updated.budget_currency,
          }
        : y,
    );
  }

  /**
   * Apply one reference percentage to every prefilled line of a grant
   * module — the equipment "global percentage" mode (#1981).
   */
  async function setModuleReferencePercentage(
    carbonReportId: number,
    moduleTypeId: number,
    percentage: number,
  ): Promise<void> {
    await api
      .patch(
        `carbon-reports/${carbonReportId}/modules/${moduleTypeId}/reference-percentage`,
        { json: { percentage } },
      )
      .json();
    await refreshAggregateIfActive();
  }

  /** Set a grant submodule's share of the budget (#1978). */
  async function setSubmoduleBudget(
    carbonReportId: number,
    moduleTypeId: number,
    submodule: string,
    budget: number | null,
  ): Promise<SimulatorPlanModule> {
    const updated = await api
      .patch(
        `carbon-reports/${carbonReportId}/modules/${moduleTypeId}/budget`,
        {
          json: { submodule, budget },
        },
      )
      .json<SimulatorPlanModule>();
    replaceModuleInYear(carbonReportId, updated);
    return updated;
  }

  async function duplicatePlan(planId: number): Promise<SimulatorPlan> {
    const plan = await api
      .post(`project-plans/${planId}/duplicate`)
      .json<SimulatorPlan>();
    markPlansStale();
    return plan;
  }

  async function deletePlan(planId: number): Promise<void> {
    await api.delete(`project-plans/${planId}`);
    markPlansStale();
  }

  return {
    plans,
    loading,
    planYears,
    planYearsLoading,
    activePlanId,
    aggregateStats,
    grantStats,
    aggregateLoading,
    plansStale,
    fetchPlans,
    setPlans,
    markPlansStale,
    createPlan,
    getPlan,
    updatePlan,
    renamePlan,
    fetchPlanYears,
    fetchAggregateStats,
    refreshAggregateIfActive,
    clearAggregate,
    setReferenceYear,
    setModuleActive,
    setModuleReferencePercentage,
    setGrantBudget,
    setSubmoduleBudget,
    duplicatePlan,
    deletePlan,
  };
});
