<template>
  <q-card flat bordered class="q-pa-lg">
    <h2 class="text-h4 q-mt-none q-mb-md">
      {{ $t('planner_project_info_title') }}
    </h2>
    <div class="row q-col-gutter-md items-start">
      <q-input
        v-model="nameInput"
        :label="$t('project_planner_name_label')"
        outlined
        dense
        class="col-12 col-md-4"
      />
      <q-input
        v-model="startYearInput"
        :label="$t('planner_start_year_label')"
        outlined
        dense
        mask="####"
        class="col-6 col-md-2"
        :rules="[yearRule]"
      />
      <q-input
        v-model="endYearInput"
        :label="$t('planner_end_year_label')"
        outlined
        dense
        mask="####"
        class="col-6 col-md-2"
        :rules="[yearRule, endAfterStartRule]"
      />
      <q-checkbox
        v-model="shareWithLab"
        :label="$t('planner_share_with_lab_label')"
        class="col-12 col-md-3"
      />
    </div>
    <div class="row justify-end q-mt-sm">
      <q-btn
        unelevated
        no-caps
        color="info"
        :label="$t('planner_project_info_save')"
        :disable="!isDirty || !isValid"
        :loading="saving"
        class="text-weight-medium"
        @click="save"
      />
    </div>
  </q-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import {
  useSimulatorPlansStore,
  type SimulatorPlan,
  type SimulatorPlanUpdatePayload,
} from 'src/stores/simulatorPlans';

const props = defineProps<{ plan: SimulatorPlan }>();
const emit = defineEmits<{ updated: [plan: SimulatorPlan] }>();

const { t } = useI18n();
const plansStore = useSimulatorPlansStore();

const nameInput = ref(props.plan.name);
const startYearInput = ref(props.plan.start_year?.toString() ?? '');
const endYearInput = ref(props.plan.end_year?.toString() ?? '');
const shareWithLab = ref(props.plan.is_viewable_by_unit_members);
const saving = ref(false);

watch(
  () => props.plan,
  (plan) => {
    nameInput.value = plan.name;
    startYearInput.value = plan.start_year?.toString() ?? '';
    endYearInput.value = plan.end_year?.toString() ?? '';
    shareWithLab.value = plan.is_viewable_by_unit_members;
  },
);

function parsedYear(value: string): number | null {
  return /^\d{4}$/.test(value) ? Number(value) : null;
}

function yearRule(value: string): boolean | string {
  if (!value) return true;
  return parsedYear(value) !== null || t('planner_year_rule_four_digits');
}

function endAfterStartRule(value: string): boolean | string {
  const start = parsedYear(startYearInput.value);
  const end = parsedYear(value);
  if (start === null || end === null) return true;
  return end >= start || t('planner_year_rule_end_after_start');
}

const isValid = computed(() => {
  const start = parsedYear(startYearInput.value);
  const end = parsedYear(endYearInput.value);
  if (startYearInput.value && start === null) return false;
  if (endYearInput.value && end === null) return false;
  if (start !== null && end !== null && end < start) return false;
  return nameInput.value.trim().length > 0;
});

const isDirty = computed(
  () =>
    nameInput.value.trim() !== props.plan.name ||
    parsedYear(startYearInput.value) !== props.plan.start_year ||
    parsedYear(endYearInput.value) !== props.plan.end_year ||
    shareWithLab.value !== props.plan.is_viewable_by_unit_members,
);

async function save() {
  if (!isDirty.value || !isValid.value || saving.value) return;
  const payload: SimulatorPlanUpdatePayload = {};
  const trimmedName = nameInput.value.trim();
  if (trimmedName !== props.plan.name) payload.name = trimmedName;
  const start = parsedYear(startYearInput.value);
  const end = parsedYear(endYearInput.value);
  if (start !== null && start !== props.plan.start_year)
    payload.start_year = start;
  if (end !== null && end !== props.plan.end_year) payload.end_year = end;
  if (shareWithLab.value !== props.plan.is_viewable_by_unit_members)
    payload.is_viewable_by_unit_members = shareWithLab.value;

  saving.value = true;
  try {
    const updated = await plansStore.updatePlan(props.plan.id, payload);
    emit('updated', updated);
  } finally {
    saving.value = false;
  }
}
</script>
