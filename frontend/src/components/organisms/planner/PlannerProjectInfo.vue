<template>
  <q-card flat bordered>
    <q-card-section class="row items-center q-gutter-sm">
      <q-icon name="o_folder_open" color="info" size="24px" />
      <span class="text-h5 text-weight-medium">
        {{ $t('planner_project_info_title') }}
      </span>
    </q-card-section>
    <q-separator />

    <q-card-section>
      <div class="text-weight-medium q-mb-sm">
        {{ $t('planner_project_label') }}
      </div>
      <q-input
        v-model="nameInput"
        :label="`${$t('project_planner_name_label')} *`"
        outlined
        dense
        hide-bottom-space
        :error="nameTouched && nameInput.trim().length === 0"
        @blur="saveIfDirty('name')"
        @keyup.enter="saveIfDirty('name')"
      />
    </q-card-section>
    <q-separator />

    <q-card-section>
      <q-checkbox
        v-model="grantProposalInput"
        :label="$t('planner_grant_proposal_checkbox')"
        color="info"
        size="sm"
      />
      <div class="text-body2 text-grey-7">
        {{ $t('planner_grant_proposal_hint') }}
      </div>
    </q-card-section>
    <q-separator />

    <q-card-section>
      <q-checkbox
        v-model="yearByYearChecked"
        :label="$t('planner_year_by_year_checkbox')"
        color="info"
        size="sm"
      />
      <div class="text-body2 text-grey-7">
        {{ $t('planner_year_by_year_hint') }}
      </div>
      <div class="row q-col-gutter-md q-mt-xs">
        <div class="col-12 col-sm-6">
          <q-select
            v-model="startYearInput"
            :label="$t('planner_start_year_label')"
            :options="startYearOptions"
            :disable="!yearByYearChecked"
            outlined
            dense
            hide-bottom-space
            emit-value
            map-options
          >
            <template #prepend>
              <q-icon name="o_calendar_month" color="info" />
            </template>
          </q-select>
        </div>
        <div class="col-12 col-sm-6">
          <q-select
            v-model="endYearInput"
            :label="$t('planner_end_year_label')"
            :options="endYearOptions"
            :disable="!yearByYearChecked"
            outlined
            dense
            hide-bottom-space
            emit-value
            map-options
          >
            <template #prepend>
              <q-icon name="o_calendar_month" color="info" />
            </template>
          </q-select>
        </div>
      </div>
    </q-card-section>
    <q-separator />

    <q-card-section>
      <q-checkbox
        v-model="shareWithLab"
        :label="$t('planner_share_with_lab_label')"
        color="info"
        size="sm"
        @update:model-value="saveIfDirty('is_viewable_by_unit_members')"
      />
    </q-card-section>
    <q-separator />

    <!-- The plan's sections (Project Grant + per-year) are created explicitly
         (not as a hidden side-effect of picking a year), with visible
         progress. -->
    <q-card-section>
      <q-btn
        unelevated
        no-caps
        size="md"
        color="info"
        class="full-width text-weight-medium"
        icon="o_playlist_add"
        :label="$t('planner_generate_sections_button')"
        :disable="!sectionsDirty || !yearsValid || !sectionTypeSelected"
        :loading="generatingSections"
        @click="generateSections"
      />
      <div v-if="!sectionTypeSelected" class="text-body2 text-negative q-mt-sm">
        {{ $t('planner_sections_need_one') }}
      </div>
      <div class="text-body2 text-grey-7 q-mt-sm">
        {{ $t('planner_generate_sections_hint') }}
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import { useRoute } from 'vue-router';

import {
  useSimulatorPlansStore,
  type SimulatorPlan,
  type SimulatorPlanUpdatePayload,
} from 'src/stores/simulatorPlans';
import { useYearConfigStore } from 'src/stores/yearConfig';

const props = defineProps<{ plan: SimulatorPlan }>();
const emit = defineEmits<{ updated: [plan: SimulatorPlan] }>();

const { t } = useI18n();
const $q = useQuasar();
const route = useRoute();
const plansStore = useSimulatorPlansStore();
const yearConfigStore = useYearConfigStore();

const nameInput = ref(props.plan.name);
const startYearInput = ref<number | null>(props.plan.start_year ?? null);
const endYearInput = ref<number | null>(props.plan.end_year ?? null);
const grantProposalInput = ref(props.plan.is_grant_proposal);
const shareWithLab = ref(props.plan.is_viewable_by_unit_members);
const nameTouched = ref(false);
const saving = ref(false);
const generatingSections = ref(false);

// Whether the plan currently has per-year sections is not a plan column; it
// is derived from its reports (a plan with none yet defaults to having them).
const persistedYearByYear = computed(() =>
  plansStore.planYears.length
    ? plansStore.planYears.some((y) => !y.is_grant)
    : true,
);
// null = untouched, mirror the persisted state (which arrives async).
const yearByYearInput = ref<boolean | null>(null);
const yearByYearChecked = computed({
  get: () => yearByYearInput.value ?? persistedYearByYear.value,
  set: (value: boolean) => (yearByYearInput.value = value),
});

watch(
  () => props.plan,
  (plan) => {
    nameInput.value = plan.name;
    startYearInput.value = plan.start_year ?? null;
    endYearInput.value = plan.end_year ?? null;
    grantProposalInput.value = plan.is_grant_proposal;
    shareWithLab.value = plan.is_viewable_by_unit_members;
    yearByYearInput.value = null;
  },
);

// Plans span from the earliest configurable Calculator year
// (settings.MIN_CONFIGURABLE_YEAR — no reference data before it) up to ten
// years ahead. Bounded selects replace free-form validation entirely.
const YEARS_AHEAD = 10;
const maxYear = computed(() => new Date().getFullYear() + YEARS_AHEAD);
const minYear = computed(
  () => yearConfigStore.minConfigurableYear ?? new Date().getFullYear(),
);

function yearRange(
  from: number,
  to: number,
  ...include: (number | null)[]
): number[] {
  const years = new Set<number>();
  for (let y = from; y <= to; y++) years.add(y);
  // Keep a stored value that falls outside the range selectable, so editing
  // an older/longer existing plan never silently drops its year.
  for (const y of include) if (y !== null) years.add(y);
  return [...years].sort((a, b) => b - a);
}

const startYearOptions = computed(() =>
  yearRange(minYear.value, maxYear.value, startYearInput.value),
);

// End year can't precede the chosen start year.
const endYearOptions = computed(() =>
  yearRange(
    Math.max(minYear.value, startYearInput.value ?? minYear.value),
    maxYear.value,
    endYearInput.value,
  ),
);

// A grant-only plan needs no year range (the grant section covers the
// whole project); year-by-year planning, or a half-set range, still
// requires both bounds.
const yearsValid = computed(() => {
  const start = startYearInput.value;
  const end = endYearInput.value;
  if (start === null && end === null) return !yearByYearChecked.value;
  return start !== null && end !== null && end >= start;
});

// Dirty vs. the persisted plan — the button is idle until the user changes
// a year or the grant checkbox, and disables again once the sections match
// the selection.
const yearsDirty = computed(
  () =>
    startYearInput.value !== (props.plan.start_year ?? null) ||
    endYearInput.value !== (props.plan.end_year ?? null),
);

const sectionsDirty = computed(
  () =>
    yearsDirty.value ||
    grantProposalInput.value !== props.plan.is_grant_proposal ||
    yearByYearChecked.value !== persistedYearByYear.value,
);

// A plan with neither year sections nor a grant section would be empty.
const sectionTypeSelected = computed(
  () => grantProposalInput.value || yearByYearChecked.value,
);

/**
 * Create/update one CarbonReport per year in the selected range, plus the
 * Project Grant report when the plan is a grant proposal. Made an explicit,
 * feedback-carrying action (button + spinner + notify) instead of a hidden
 * side-effect of picking a year — the backend syncs the reports.
 */
async function generateSections() {
  const start = startYearInput.value;
  const end = endYearInput.value;
  if (!yearsValid.value || generatingSections.value) return;

  const payload: SimulatorPlanUpdatePayload = {
    is_grant_proposal: grantProposalInput.value,
    with_year_sections: yearByYearChecked.value,
  };
  if (start !== null && end !== null) {
    payload.start_year = start;
    payload.end_year = end;
    payload.default_reference_year = Number(route.params.year);
  }

  generatingSections.value = true;
  try {
    const updated = await plansStore.updatePlan(props.plan.id, payload);
    yearByYearInput.value = null;
    emit('updated', updated);
    $q.notify({ type: 'positive', message: t('planner_sections_generated') });
  } catch {
    $q.notify({
      type: 'negative',
      message: t('planner_sections_generate_error'),
    });
  } finally {
    generatingSections.value = false;
  }
}

/**
 * Persist name / lab-visibility as soon as the user leaves the field (the
 * design has no explicit Save button). Years are handled by generateYears.
 */
async function saveIfDirty(field: 'name' | 'is_viewable_by_unit_members') {
  if (field === 'name') nameTouched.value = true;
  if (saving.value) return;

  const payload: SimulatorPlanUpdatePayload = {};
  const trimmedName = nameInput.value.trim();

  if (field === 'name' && trimmedName && trimmedName !== props.plan.name) {
    payload.name = trimmedName;
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
  } catch {
    nameInput.value = props.plan.name;
    shareWithLab.value = props.plan.is_viewable_by_unit_members;
  } finally {
    saving.value = false;
  }
}
</script>
