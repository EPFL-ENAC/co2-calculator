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
      <q-card flat class="container">
        <q-icon
          name="o_calendar_month"
          color="info"
          size="32px"
          class="q-mb-md"
        />
        <h1 class="text-h2 q-mb-md">{{ $t('project_planner_page_title') }}</h1>
        <p class="text-body1 q-mb-none">
          {{ $t('project_planner_page_intro') }}
        </p>
      </q-card>

      <q-card flat bordered class="q-pa-lg">
        <div class="row items-end q-gutter-md">
          <q-input
            v-model="nameInput"
            :label="$t('project_planner_name_label')"
            outlined
            dense
            class="col"
            @keyup.enter="saveName"
          />
          <q-btn
            unelevated
            no-caps
            color="info"
            :label="$t('project_planner_name_save')"
            :disable="!canSave"
            :loading="saving"
            size="md"
            class="text-weight-medium"
            @click="saveName"
          />
        </div>
      </q-card>
    </template>
  </q-page>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import {
  useSimulatorPlansStore,
  type SimulatorPlan,
} from 'src/stores/simulatorPlans';
import { useWorkspaceStore } from 'src/stores/workspace';

const route = useRoute();
const router = useRouter();
const workspaceStore = useWorkspaceStore();
const plansStore = useSimulatorPlansStore();

// workspaceGuard ensures selectedUnit is always set before this route renders
// (same invariant as SimulationExplorePage).
const unitId = computed(() => workspaceStore.selectedUnit!.id);

const plan = ref<SimulatorPlan | null>(null);
const notFound = ref(false);
const nameInput = ref('');
const saving = ref(false);

const canSave = computed(() => {
  const trimmed = nameInput.value.trim();
  return trimmed.length > 0 && trimmed !== plan.value?.name;
});

async function saveName() {
  if (!plan.value || !canSave.value || saving.value) return;
  saving.value = true;
  try {
    const updated = await plansStore.renamePlan(
      plan.value.id,
      nameInput.value.trim(),
    );
    plan.value = updated;
    nameInput.value = updated.name;
    // Param-only replace keeps this component instance mounted.
    await router.replace({
      name: 'project-planner',
      params: { ...route.params, name: updated.name },
    });
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  try {
    plan.value = await plansStore.getPlanByName(
      unitId.value,
      String(route.params.name),
    );
    nameInput.value = plan.value.name;
  } catch {
    notFound.value = true;
  }
});
</script>
