<template>
  <q-card flat bordered>
    <q-card-section class="row items-center q-gutter-sm">
      <q-icon name="o_folder_open" color="negative" size="24px" />
      <span class="text-h5">{{ $t('planner_project_info_title') }}</span>
    </q-card-section>
    <q-separator />

    <q-card-section>
      <div class="text-weight-bold q-mb-sm">
        {{ $t('planner_project_label') }}
      </div>
      <q-input
        v-model="nameInput"
        :label="`${$t('project_planner_name_label')} *`"
        outlined
        dense
        :error="nameTouched && nameInput.trim().length === 0"
        @blur="saveIfDirty('name')"
        @keyup.enter="saveIfDirty('name')"
      />
    </q-card-section>
    <q-separator />

    <q-card-section>
      <div class="text-weight-bold q-mb-sm">
        {{ $t('planner_year_selection_label') }}
      </div>
      <div class="row q-col-gutter-md">
        <div class="col-12 col-sm-6">
          <q-input
            v-model="startYearInput"
            :label="$t('planner_start_year_label')"
            outlined
            dense
            mask="####"
            :rules="[yearRule, minYearRule]"
            @blur="saveIfDirty('start_year')"
          >
            <template #prepend>
              <q-icon name="o_calendar_month" color="negative" />
            </template>
          </q-input>
        </div>
        <div class="col-12 col-sm-6">
          <q-input
            v-model="endYearInput"
            :label="$t('planner_end_year_label')"
            outlined
            dense
            mask="####"
            :rules="[yearRule, endAfterStartRule]"
            @blur="saveIfDirty('end_year')"
          >
            <template #prepend>
              <q-icon name="o_calendar_month" color="negative" />
            </template>
          </q-input>
        </div>
      </div>
    </q-card-section>
    <q-separator />

    <q-card-section>
      <q-checkbox
        v-model="shareWithLab"
        :label="$t('planner_share_with_lab_label')"
        color="negative"
        @update:model-value="saveIfDirty('is_viewable_by_unit_members')"
      />
    </q-card-section>
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
import { useYearConfigStore } from 'src/stores/yearConfig';

const props = defineProps<{ plan: SimulatorPlan }>();
const emit = defineEmits<{ updated: [plan: SimulatorPlan] }>();

const { t } = useI18n();
const plansStore = useSimulatorPlansStore();
const yearConfigStore = useYearConfigStore();

const nameInput = ref(props.plan.name);
const startYearInput = ref(props.plan.start_year?.toString() ?? '');
const endYearInput = ref(props.plan.end_year?.toString() ?? '');
const shareWithLab = ref(props.plan.is_viewable_by_unit_members);
const nameTouched = ref(false);
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

// Start year cannot precede the earliest configurable Calculator year
// (settings.MIN_CONFIGURABLE_YEAR) — there is no reference data before it.
// When the bound isn't loaded yet, don't block.
function minYearRule(value: string): boolean | string {
  const year = parsedYear(value);
  const min = yearConfigStore.minConfigurableYear;
  if (year === null || min === null) return true;
  return (
    year >= min || t('planner_year_rule_min_year', { year: min })
  );
}

function endAfterStartRule(value: string): boolean | string {
  const start = parsedYear(startYearInput.value);
  const end = parsedYear(value);
  if (start === null || end === null) return true;
  return end >= start || t('planner_year_rule_end_after_start');
}

const rangeValid = computed(() => {
  const start = parsedYear(startYearInput.value);
  const end = parsedYear(endYearInput.value);
  const min = yearConfigStore.minConfigurableYear;
  if (startYearInput.value && start === null) return false;
  if (endYearInput.value && end === null) return false;
  if (start !== null && min !== null && start < min) return false;
  return start === null || end === null || end >= start;
});

/**
 * Persist a single field as soon as the user leaves it (the design has no
 * explicit Save button). Each field only PATCHes when its own value changed
 * and the whole form is valid, so a half-typed year never round-trips.
 */
async function saveIfDirty(
  field: 'name' | 'start_year' | 'end_year' | 'is_viewable_by_unit_members',
) {
  if (field === 'name') nameTouched.value = true;
  if (saving.value || !rangeValid.value) return;

  const payload: SimulatorPlanUpdatePayload = {};
  const trimmedName = nameInput.value.trim();
  const start = parsedYear(startYearInput.value);
  const end = parsedYear(endYearInput.value);

  if (field === 'name' && trimmedName && trimmedName !== props.plan.name) {
    payload.name = trimmedName;
  }
  if (field === 'start_year' && start !== null && start !== props.plan.start_year) {
    payload.start_year = start;
  }
  if (field === 'end_year' && end !== null && end !== props.plan.end_year) {
    payload.end_year = end;
  }
  if (
    field === 'is_viewable_by_unit_members' &&
    shareWithLab.value !== props.plan.is_viewable_by_unit_members
  ) {
    payload.is_viewable_by_unit_members = shareWithLab.value;
  }
  if (Object.keys(payload).length === 0) return;

  saving.value = true;
  try {
    emit('updated', await plansStore.updatePlan(props.plan.id, payload));
  } finally {
    saving.value = false;
  }
}
</script>
