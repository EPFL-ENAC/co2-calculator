import { ref } from 'vue';
import { defineStore } from 'pinia';
import { api } from 'src/api/http';

/**
 * Hand-typed DTO mirroring backend/app/schemas/simulator_plan.py; re-run
 * `cd frontend && make gen-api-types` against an up-to-date backend to
 * replace with generated `paths['/project-plans/...']` types.
 */
export interface SimulatorPlan {
  id: number;
  unit_id: number;
  name: string;
  created_by: number | null;
  created_at: string | null;
  creator_name: string | null;
}

export const useSimulatorPlansStore = defineStore('simulatorPlans', () => {
  const plans = ref<SimulatorPlan[]>([]);
  const loading = ref(false);

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

  async function renamePlan(
    planId: number,
    name: string,
  ): Promise<SimulatorPlan> {
    return api
      .patch(`project-plans/${planId}`, { json: { name } })
      .json<SimulatorPlan>();
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
    fetchPlans,
    createPlan,
    getPlanByName,
    renamePlan,
    duplicatePlan,
    deletePlan,
  };
});
