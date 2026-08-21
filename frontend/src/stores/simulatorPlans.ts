import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from 'src/api/http';
import { pollUntilPrefilled } from 'src/composables/pollUntilPrefilled';
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
  /** Set when the PATCH deferred its prefill to a background job; poll it
   * before trusting the plan years (backend plan #2050 Track F4). */
  prefill_job_id?: number | null;
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
  /** See {@link SimulatorPlan.prefill_job_id}. */
  prefill_job_id?: number | null;
}

export interface SimulatorPlanPrefillStatus {
  job_id: number;
  finished: boolean;
  result: string | null;
  status_message: string | null;
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

  // True while a deferred prefill job is still running for the open plan —
  // its year sections exist but are still empty, so the page shows a
  // "building" state instead of a misleading zero (plan #2050 Track F4).
  const prefillRunning = ref(false);

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
   * Wait for a deferred prefill job to reach its terminal state.
   *
   * The plan PATCHes persist their metadata change immediately and hand the
   * (potentially tens of thousands of rows) copy of a reference year to a
   * background job. Until it finishes the year sections are empty, so the
   * caller must not render them as real results.
   */
  async function waitForPrefill(
    planId: number,
    jobId: number,
  ): Promise<SimulatorPlanPrefillStatus | null> {
    prefillRunning.value = true;
    try {
      return await pollUntilPrefilled(() =>
        api
          .get(`project-plans/${planId}/prefill/${jobId}`)
          .json<SimulatorPlanPrefillStatus>(),
      );
    } finally {
      prefillRunning.value = false;
    }
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
      .patch(`project-plans/${planId}`, { json: payload })
      .json<SimulatorPlan>();

    markPlansStale();
    // New year sections are created empty and filled by a background job;
    // refetching before it finishes would show them as legitimately zero.
    if (plan.prefill_job_id != null) {
      await waitForPrefill(planId, plan.prefill_job_id);
    }
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
      })
      .json<SimulatorPlanYear>();
    planYears.value = planYears.value.map((y) =>
      y.id === updated.id ? updated : y,
    );
    // `updated` was serialised before the prefill ran, so its modules are
    // still empty — wait, then refetch to get the copied rows and stats.
    if (updated.prefill_job_id != null) {
      await waitForPrefill(planId, updated.prefill_job_id);
      await fetchPlanYears(planId);
    }
    await refreshAggregateIfActive();
    return planYears.value.find((y) => y.id === updated.id) ?? updated;
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
    prefillRunning,
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
