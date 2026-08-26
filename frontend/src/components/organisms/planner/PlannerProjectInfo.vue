<template>
  <q-card flat bordered>
    <q-card-section class="row items-center q-gutter-sm">
      <q-icon name="o_folder_open" color="info" size="24px" />
      <span class="text-h5 text-weight-medium">
        {{ $t('planner_project_info_title') }}
      </span>
      <q-icon
        v-if="sectionTooltip"
        :name="outlinedInfo"
        size="16px"
        color="grey-6"
        class="cursor-pointer"
        :aria-label="$t('module-info-label')"
      >
        <q-tooltip anchor="center right" self="top right" class="u-tooltip">
          {{ sectionTooltip }}
        </q-tooltip>
      </q-icon>
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
        @blur="saveName"
        @keyup.enter="saveName"
      />
      <q-checkbox
        v-model="isViewableByUnitMembers"
        :label="$t('planner_share_with_lab_label')"
        :disable="yearByYearChecked"
        color="info"
        size="sm"
        class="q-mt-sm"
      />
      <div v-if="yearByYearChecked" class="text-body2 text-grey-7">
        {{ $t('planner_share_with_lab_disabled_hint') }}
      </div>
    </q-card-section>
    <q-separator />

    <q-card-section>
      <div class="row items-center q-gutter-x-sm">
        <q-checkbox
          v-model="grantProposalInput"
          :label="$t('planner_grant_proposal_checkbox')"
          color="info"
          size="sm"
        />
        <q-icon
          v-if="grantProposalTooltip"
          :name="outlinedInfo"
          size="16px"
          color="grey-6"
          class="cursor-pointer"
          :aria-label="$t('module-info-label')"
        >
          <q-tooltip anchor="center right" self="top right" class="u-tooltip">
            {{ grantProposalTooltip }}
          </q-tooltip>
        </q-icon>
      </div>
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
import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { useQuasar } from 'quasar';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import { runtimeConfig } from 'src/config/runtime';
import { pickDefaultYear } from 'src/router/guards/redirectToDefaultRoute';
import { useYearConfigStore } from 'src/stores/yearConfig';

import {
  useSimulatorPlansStore,
  type SimulatorPlan,
  type SimulatorPlanUpdatePayload,
} from 'src/stores/simulatorPlans';

const props = defineProps<{ plan: SimulatorPlan }>();
const emit = defineEmits<{ updated: [plan: SimulatorPlan] }>();

const { t } = useI18n();
const $q = useQuasar();
const plansStore = useSimulatorPlansStore();
const yearConfigStore = useYearConfigStore();

const sectionTooltip = computed(() => t('planner-project-info-section-title'));
const grantProposalTooltip = computed(() => t('planner-grant-proposal-title'));

const nameInput = ref(props.plan.name);
const startYearInput = ref<number | null>(props.plan.start_year ?? null);
const endYearInput = ref<number | null>(props.plan.end_year ?? null);
const grantProposalInput = ref(props.plan.is_grant_proposal);
const nameTouched = ref(false);
const saving = ref(false);
const generatingSections = ref(false);

// Whether the plan currently has per-year sections is not a plan column; it
// is derived from its reports (a plan with none yet starts without them,
// like the grant checkbox).
const persistedYearByYear = computed(() =>
  plansStore.planYears.length
    ? plansStore.planYears.some((y) => !y.is_grant)
    : false,
);
// null = untouched, mirror the persisted state (which arrives async).
const yearByYearInput = ref<boolean | null>(null);
const yearByYearChecked = computed({
  get: () => yearByYearInput.value ?? persistedYearByYear.value,
  set: (value: boolean) => (yearByYearInput.value = value),
});

// Per-year sections hold the unit's real annual data, so a plan carrying them
// stays private to its creator: the share checkbox reads unchecked and is
// locked while "Detailed per year" is on. Derived straight from the plan (the
// save round-trip refreshes it), so there is no local copy to keep in sync.
const isViewableByUnitMembers = computed({
  get: () => props.plan.is_viewable_by_unit_members && !yearByYearChecked.value,
  set: (value: boolean) => void saveShareWithLab(value),
});

// Project horizon (steering-committee decision, per-pod configurable via
// APP_PLANNER_MIN_YEAR / APP_PLANNER_MAX_YEAR). Bounded selects replace
// free-form validation entirely.
const MIN_YEAR = runtimeConfig.plannerMinYear;
const MAX_YEAR = runtimeConfig.plannerMaxYear;

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
  yearRange(MIN_YEAR, MAX_YEAR, startYearInput.value),
);

// End year can't precede the chosen start year.
const endYearOptions = computed(() =>
  yearRange(
    Math.max(MIN_YEAR, startYearInput.value ?? MIN_YEAR),
    MAX_YEAR,
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

// Default reference year is today's year - 1; when that year isn't open
// in the Calculator, fall back to the latest open year.
function defaultReferenceYear(): number {
  const target = new Date().getFullYear() - 1;
  const open = yearConfigStore.startedYears;
  return open.has(target) ? target : pickDefaultYear(open);
}

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

  const grantSectionAdded =
    grantProposalInput.value && !props.plan.is_grant_proposal;
  const payload: SimulatorPlanUpdatePayload = {
    is_grant_proposal: grantProposalInput.value,
    with_year_sections: yearByYearChecked.value,
  };
  if (start !== null && end !== null) {
    payload.start_year = start;
    payload.end_year = end;
    payload.default_reference_year = defaultReferenceYear();
  }

  generatingSections.value = true;
  try {
    const updated = await plansStore.updatePlan(props.plan.id, payload);
    yearByYearInput.value = null;
    if (grantSectionAdded) await defaultGrantReferenceYear();
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

async function defaultGrantReferenceYear() {
  const grantYear = plansStore.planYears.find(
    (y) => y.is_grant && y.reference_year === null,
  );
  if (!grantYear) return;
  try {
    await plansStore.setReferenceYear(
      props.plan.id,
      grantYear.year,
      defaultReferenceYear(),
      true,
    );
  } catch {
    $q.notify({ type: 'negative', message: t('planner_reference_year_error') });
  }
}

/**
 * Persist name / lab-visibility as soon as the user leaves the field (the
 * design has no explicit Save button). Years are handled by generateSections.
 */
async function saveName() {
  nameTouched.value = true;
  if (saving.value) return;

  const trimmedName = nameInput.value.trim();
  if (!trimmedName || trimmedName === props.plan.name) return;

  saving.value = true;
  try {
    emit(
      'updated',
      await plansStore.updatePlan(props.plan.id, { name: trimmedName }),
    );
  } catch {
    nameInput.value = props.plan.name;
  } finally {
    saving.value = false;
  }
}

async function saveShareWithLab(value: boolean) {
  if (saving.value || value === props.plan.is_viewable_by_unit_members) return;

  saving.value = true;
  try {
    emit(
      'updated',
      await plansStore.updatePlan(props.plan.id, {
        is_viewable_by_unit_members: value,
      }),
    );
  } catch {
    // the checkbox re-derives from the untouched plan
  } finally {
    saving.value = false;
  }
}
</script>
