<template>
  <q-page class="page-grid">
    <q-card v-if="notFound" flat class="container">
      <q-icon
        name="o_calendar_month"
        color="info"
        size="32px"
        class="q-mb-md"
      />
      <h1 class="text-h2 q-mb-md">{{ $t('project_planner_page_title') }}</h1>
      <p class="text-body1 q-mb-md">
        {{ $t('project_planner_not_found') }}
      </p>
      <q-btn
        unelevated
        no-caps
        color="info"
        :label="$t('project_planner_back_home')"
        class="text-weight-medium"
        :to="{ name: 'home' }"
      />
    </q-card>

    <template v-else-if="plan">
      <!-- Title box -->
      <q-card flat bordered class="container q-pa-lg">
        <q-icon name="o_tune" color="negative" size="32px" class="q-mb-md" />
        <h1 class="text-h3 q-mt-none q-mb-sm">
          {{ $t('planner_page_title') }}
        </h1>
        <p class="text-body1 q-mb-none text-grey-8">
          {{ $t('planner_page_intro') }}
          <q-icon name="o_info" size="18px" class="q-ml-xs cursor-pointer">
            <q-tooltip max-width="320px">
              {{ $t('planner_methodology_tooltip') }}
            </q-tooltip>
          </q-icon>
        </p>
      </q-card>

      <!-- Project information box -->
      <planner-project-info :plan="plan" @updated="onPlanUpdated" />

      <!-- One section per year of the range -->
      <template v-if="plansStore.planYears.length">
        <planner-year-section
          v-for="yearData in plansStore.planYears"
          :key="yearData.id"
          :plan-id="plan.id"
          :year-data="yearData"
          :unit-id="unitId"
          :reference-year-options="referenceYearOptions"
          :expanded-key="expandedKey"
          @update:expanded-key="expandedKey = $event"
        />
      </template>
      <q-card v-else flat bordered class="q-pa-lg">
        <p class="text-body1 q-mb-none text-grey-8">
          {{ $t('planner_no_years_hint') }}
        </p>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import PlannerProjectInfo from 'src/components/organisms/planner/PlannerProjectInfo.vue';
import PlannerYearSection from 'src/components/organisms/planner/PlannerYearSection.vue';
import {
  useSimulatorPlansStore,
  type SimulatorPlan,
} from 'src/stores/simulatorPlans';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';

const route = useRoute();
const router = useRouter();
const workspaceStore = useWorkspaceStore();
const plansStore = useSimulatorPlansStore();
const yearConfigStore = useYearConfigStore();

// workspaceGuard ensures selectedUnit is always set before this route renders
// (same invariant as SimulationExplorePage).
const unitId = computed(() => workspaceStore.selectedUnit!.id);

const plan = ref<SimulatorPlan | null>(null);
const notFound = ref(false);
// `${year}-${module}` of the single expanded module across all year
// sections — the module store holds one module's data at a time.
const expandedKey = ref<string | null>(null);

// Reference years are constrained to years open in the Calculator.
const referenceYearOptions = computed(() =>
  [...yearConfigStore.startedYears]
    .sort((a, b) => b - a)
    .map((year) => ({ label: String(year), value: year })),
);

async function onPlanUpdated(updated: SimulatorPlan) {
  const renamed = plan.value !== null && plan.value.name !== updated.name;
  plan.value = updated;
  if (renamed) {
    // Param-only replace keeps this component instance mounted.
    await router.replace({
      name: 'project-planner',
      params: { ...route.params, name: updated.name },
    });
  }
}

onMounted(async () => {
  try {
    plan.value = await plansStore.getPlanByName(
      unitId.value,
      String(route.params.name),
    );
  } catch {
    notFound.value = true;
    return;
  }
  await Promise.all([
    plansStore.fetchPlanYears(plan.value.id),
    yearConfigStore.fetchConfiguredYears(),
  ]);
});
</script>
