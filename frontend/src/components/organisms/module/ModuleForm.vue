<template>
  <q-card flat>
    <q-card-section
      class="row flex justify-between items-center q-mx-lg q-my-xl"
    >
      <div class="text-h3 text-weight-medium q-mb-none">
        {{ $t(`${moduleType}-${submoduleType}-form-title`) }}
      </div>

      <q-icon
        v-if="hasTooltip"
        :name="outlinedInfo"
        size="sm"
        class="cursor-pointer"
        :aria-label="$t(`${moduleType}-${submoduleType}-form-title-info-label`)"
      >
        <q-tooltip
          v-if="typeof hasTooltip === 'string'"
          anchor="center right"
          self="top right"
          class="u-tooltip"
        >
          {{ $t(hasTooltip) }}
        </q-tooltip>
      </q-icon>
    </q-card-section>

    <q-card-section v-if="hasSubtitle" class="q-mx-lg q-my-xl text-subtitle1">
      {{ $t(`${moduleType}-${submoduleType}-form-subtitle`) }}
    </q-card-section>
    <q-card-section v-if="hasStudentHelper">
      <q-card flat bordered class="q-pa-none">
        <q-expansion-item
          flat
          bordered
          header-class="text-h5 text-weight-medium"
        >
          <template #header>
            <div class="row flex items-center full-width">
              <q-icon
                name="o_calculate"
                size="sm"
                class="q-mr-sm"
                color="accent"
              />
              <div class="col">
                {{ $t(`student_helper_title`) }}
              </div>
            </div>
          </template>
          <q-separator />
          <StudentFTECalculator @use-value="onUseCalculatedFTE" />
        </q-expansion-item>
      </q-card>
    </q-card-section>

    <q-card-section class="q-pa-none">
      <q-form @submit.prevent="onSubmit">
        <div class="q-mx-lg q-my-xl">
          <div v-if="visibleFields.length === 0" class="text-subtle">
            No form configured
          </div>

          <div class="form-grid">
            <div
              v-for="inp in visibleFieldsWithConditional"
              :key="inp.id"
              :class="['form-field', getGridClass(getDynamicRatio(inp))]"
            >
              <template v-if="inp.type === 'date'">
                <DateInput
                  v-model="form[inp.id]"
                  :module-type="props.moduleType"
                  :submodule-type="props.submoduleType"
                  :field="inp"
                  :entry="form"
                  :selected-year="selectedYear"
                  :errors="errors[inp.id]"
                />
              </template>
              <template v-else-if="inp.type === 'direction-input'">
                <DestinationInput
                  v-model="form[inp.id]"
                  :module-type="props.moduleType"
                  :submodule-type="props.submoduleType"
                  :field="inp"
                  :entry="form"
                  :from="String(form.origin ?? '')"
                  :to="String(form.destination ?? '')"
                  :error="!!errors.origin || !!errors.destination"
                  :error-message="errors.origin || errors.destination || ''"
                  :transport-mode="getTravelMode()"
                  :origin-location-id="form.origin_location_id"
                  :destination-location-id="form.destination_location_id"
                  :number-of-trips="Number(form.number_of_trips) || 1"
                  @update:from="
                    (val) => {
                      form.origin = val;
                      onDataUpdate();
                    }
                  "
                  @update:to="
                    (val) => {
                      form.destination = val;
                      onDataUpdate();
                    }
                  "
                  @update:origin-location-id="
                    (id) => {
                      form.origin_location_id = id;
                    }
                  "
                  @update:destination-location-id="
                    (id) => {
                      form.destination_location_id = id;
                    }
                  "
                  @distance-calculated="
                    (val) => {
                      form.distance_km = val;
                    }
                  "
                />
              </template>
              <FieldInput
                v-else
                v-model="form[inp.id]"
                :module-type="props.moduleType"
                :submodule-type="props.submoduleType"
                :field="inp"
                :entry="form"
                :errors="errors[inp.id]"
                @update:model-value="onDataUpdate"
              />
            </div>
          </div>
        </div>

        <q-separator />

        <q-card-actions class="action-no-margin q-mx-lg q-my-xl">
          <template v-if="rowData">
            <!-- Edit mode buttons -->
            <q-btn
              outline
              color="grey-4"
              text-color="primary"
              :label="$t('common_cancel')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium"
              @click="$emit('edit', null)"
            />
            <q-btn
              icon="o_save"
              color="accent"
              :label="$t('common_save')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium"
              type="submit"
            />
          </template>
          <template v-else>
            <!-- Add mode buttons -->
            <q-btn
              icon="o_add_circle"
              color="accent"
              :label="$t(addButtonLabelKey)"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium"
              type="submit"
              @click="clearOriginAndDestination"
            />
            <q-btn
              v-if="hasAddWithNote"
              outline
              icon="o_add_comment"
              color="primary"
              :label="$t('common_add_with_note_button')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium q-mr-sm"
              @click="openAddNoteDialog"
            />
          </template>
        </q-card-actions>
      </q-form>
    </q-card-section>
    <NoteDialog v-model="addNoteDialogOpen" @save="saveNote" />
  </q-card>
</template>

<script setup lang="ts">
import { reactive, watch, computed, ref } from 'vue';

import type { ModuleField } from 'src/constant/moduleConfig';
import { useWorkspaceStore } from 'src/stores/workspace';
import { QIcon } from 'quasar';
import { useI18n } from 'vue-i18n';
import StudentFTECalculator from './StudentFTECalculator.vue';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import DestinationInput from 'src/components/atoms/CO2DestinationInput.vue';
import DateInput from 'src/components/atoms/CO2DateInput.vue';
import FieldInput from 'src/components/atoms/CO2ModuleFieldInput.vue';
import NoteDialog from 'src/components/molecules/NoteDialog.vue';
import type { AllSubmoduleTypes, Module } from 'src/constant/modules';
import {
  MODULES,
  SUBMODULE_PROFESSIONAL_TRAVEL_TYPES,
} from 'src/constant/modules';

const { t: $t } = useI18n();
const workspaceStore = useWorkspaceStore();

const addNoteDialogOpen = ref(false);

interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;

const props = withDefaults(
  defineProps<{
    fields?: ModuleField[] | null;
    rowData?: Record<string, FieldValue> | null;
    submoduleType: AllSubmoduleTypes;
    moduleType: Module | string;
    hasTooltip?: boolean | string;
    hasSubtitle?: boolean;
    hasStudentHelper?: boolean;
    hasAddWithNote?: boolean;
    addButtonLabelKey?: string;
    unitId?: number;
    year?: string | number;
  }>(),
  {
    fields: null,
    rowData: null,
    hasTooltip: true,
    hasSubtitle: false,
    hasStudentHelper: false,
    hasAddWithNote: true,
    addButtonLabelKey: 'common_add_button',
    unitId: undefined,
    year: undefined,
  },
);

const selectedYear = computed(
  () => workspaceStore.selectedYear ?? new Date().getFullYear(),
);

const visibleFields = computed(() =>
  (props.fields ?? []).filter((f) => !f.hideIn?.form),
);

// Generic conditional visibility handling
const visibleFieldsWithConditional = computed(() => {
  return visibleFields.value.filter((f) => {
    if (f.visible) {
      const isVisible = f.visible(props.submoduleType, form);
      if (!isVisible) {
        // Clear value and error for hidden field
        form[f.id] = null;
        errors[f.id] = null;
      }
      return isVisible;
    }
    return true;
  });
});

function onDataUpdate() {
  // This function is called whenever a field value is updated
  // console.log('Data updated:', form);
}

// Generic dynamic ratio handling
function getDynamicRatio(inp: ModuleField): string | undefined {
  if (inp.conditionalRatio) {
    const { when, ratio } = inp.conditionalRatio;
    const fieldValue = form[when.fieldId];
    if (fieldValue === when.value) {
      return ratio;
    }
  }

  return inp.ratio;
}

const emit = defineEmits<{
  (e: 'submit', payload: Record<string, FieldValue>): void;
  (e: 'edit', payload: Record<string, FieldValue> | null): void;
}>();
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const form = reactive<Record<string, any>>({});
const errors = reactive<Record<string, string | null>>({});

function getTravelMode(): 'plane' | 'train' | undefined {
  if (props.moduleType !== MODULES.ProfessionalTravel) return undefined;
  if (props.submoduleType === SUBMODULE_PROFESSIONAL_TRAVEL_TYPES.Plane)
    return 'plane';
  if (props.submoduleType === SUBMODULE_PROFESSIONAL_TRAVEL_TYPES.Train)
    return 'train';
  return undefined;
}

function validateUsage(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return { valid: false, parsed: null, error: 'Required' };
  }
  const n = Number(value);
  if (!Number.isFinite(n))
    return { valid: false, parsed: null, error: 'Number required' };
  if (n < 0) return { valid: false, parsed: null, error: 'Must be >= 0' };
  if (n > 168) return { valid: false, parsed: null, error: 'Max 168 hrs/wk' };
  return { valid: true, parsed: n, error: null };
}

async function init() {
  if (props.rowData) {
    Object.keys(props.rowData).forEach((key) => {
      form[key] = props.rowData[key];
      errors[key] = null;
    });
    return;
  }
  for (const i of visibleFields.value) {
    const effectiveType = i.type;
    if (props.rowData && props.rowData[i.id] !== undefined) {
      form[i.id] = props.rowData[i.id];
    } else {
      // Check if field has a default value
      if (i.default !== undefined) {
        if (typeof i.default === 'function') {
          form[i.id] = await i.default(props.submoduleType, form);
        } else {
          form[i.id] = i.default;
        }
      } else {
        switch (effectiveType) {
          case 'checkbox':
          case 'boolean':
            form[i.id] = false;
            break;
          case 'number':
            form[i.id] = null;
            break;
          case 'direction-input':
            // Initialize origin and destination fields separately
            if (!form.origin) form.origin = '';
            if (!form.destination) form.destination = '';
            // Initialize location IDs (only for new entries, not editing)
            if (!props.rowData) {
              if (!form.origin_location_id) form.origin_location_id = undefined;
              if (!form.destination_location_id)
                form.destination_location_id = undefined;
            }
            break;
          default:
            // Use null for select fields, empty string for text fields
            form[i.id] = effectiveType === 'select' ? null : '';
        }
      }
    }
    errors[i.id] = null;
  }
}

// re-init when inputs or rowData change (e.g. dynamic config or edit mode)
watch(
  () => [props.fields, props.rowData],
  () => init(),
  { deep: true, immediate: true },
);

function validateField(i: ModuleField) {
  const v = form[i.id];
  const effectiveType = i.type;
  errors[i.id] = null;

  if (i.id === 'active_usage_hours' || i.id === 'passive_usage_hours') {
    const validation = validateUsage(v);
    if (!validation.valid) {
      errors[i.id] = validation.error;
      return false;
    }
    form[i.id] = validation.parsed as FieldValue;
    return true;
  }

  // Handle direction-input validation (check origin and destination)
  if (effectiveType === 'direction-input') {
    // Clear previous errors
    errors.origin = null;
    errors.destination = null;

    if (i.required) {
      if (!form.origin || form.origin === '') {
        errors.origin = 'Required';
        return false;
      }
      if (!form.destination || form.destination === '') {
        errors.destination = 'Required';
        return false;
      }
    }

    // Check if origin and destination are the same
    const originValue = String(form.origin || '').trim();
    const destinationValue = String(form.destination || '').trim();
    if (originValue && destinationValue && originValue === destinationValue) {
      const errorMessage = $t(
        `${MODULES.ProfessionalTravel}-error-same-destination`,
      );
      errors.origin = errorMessage;
      errors.destination = errorMessage;
      return false;
    }

    return !errors.origin && !errors.destination;
  }

  if (i.required) {
    if (effectiveType === 'checkbox' || effectiveType === 'boolean') {
      if (!v) errors[i.id] = 'Required';
    } else if (v === '' || v === null || v === undefined) {
      errors[i.id] = 'Required';
    }
  }
  if (effectiveType === 'number' && v !== '' && v !== null && v !== undefined) {
    const n = Number(v);
    if (Number.isNaN(n)) errors[i.id] = 'Must be a number';
    if (i.min !== undefined && n < i.min) errors[i.id] = `Min ${i.min}`;
    if (i.max !== undefined && n > i.max) errors[i.id] = `Max ${i.max}`;
  }
  return !errors[i.id];
}

function validateForm() {
  let ok = true;
  visibleFields.value.forEach((i) => {
    if (!validateField(i)) {
      console.log(`[ModuleForm] Validation FAILED for field "${i.id}":`, {
        value: form[i.id],
        type: i.type,
        required: i.required,
        error: errors[i.id],
      });
      ok = false;
    }
  });

  return ok;
}

function buildPayload(): Record<
  string,
  string | number | boolean | null | Option
> {
  const payload: Record<string, string | number | boolean | null | Option> = {};

  const excludedFields = [
    'origin_location_data',
    'destination_location_data',
    'origin',
    'destination',
    'round_trip',
    'distance_km',
    'kg_co2eq',
  ];

  Object.keys(form).forEach((k) => {
    if (excludedFields.includes(k)) return;

    const cfg = visibleFields.value.find((i) => i.id === k);
    const effectiveType = cfg?.type;
    const val = form[k];

    if (effectiveType === 'number') {
      payload[k] = val === null || val === '' ? null : Number(val);
    } else {
      payload[k] = val as FieldValue;
    }
  });

  if (
    !props.rowData &&
    form.origin_location_id !== undefined &&
    form.destination_location_id !== undefined
  ) {
    payload.origin_location_id = form.origin_location_id as number;
    payload.destination_location_id = form.destination_location_id as number;
  }

  return payload;
}

function onSubmit() {
  if (!validateForm()) return;
  emit('submit', buildPayload());
  reset();
}

function reset() {
  visibleFields.value.forEach((i) => {
    const effectiveType = i.type;
    // Check if field has a default value
    if (i.default !== undefined) {
      form[i.id] = i.default;
    } else if (effectiveType === 'checkbox' || effectiveType === 'boolean')
      form[i.id] = false;
    else if (effectiveType === 'number') form[i.id] = null;
    else if (effectiveType === 'direction-input') {
      // Clear origin and destination fields
      form.origin = '';
      form.destination = '';
      // Reset location IDs
      form.origin_location_id = undefined;
      form.destination_location_id = undefined;
      form.distance_km = null;
    } else {
      // Use null for select fields, empty string for text fields
      form[i.id] = effectiveType === 'select' ? null : '';
    }
    errors[i.id] = null;
  });
}

function getGridClass(ratio?: string): string {
  if (!ratio) return 'form-field--full';
  // Parse ratio like "3/4" -> calculate grid span
  const [numerator, denominator] = ratio.split('/').map(Number);
  if (!numerator || !denominator) return 'form-field--full';
  const span = Math.round((numerator / denominator) * 12);
  return `form-field--span-${span}`;
}

function onUseCalculatedFTE(value: number) {
  form['fte'] = value;
}

function clearOriginAndDestination() {
  // Clear origin and destination fields when add button is clicked
  // This ensures fields are cleared after successful form submission
  // The reset() function will handle the actual clearing
}

function openAddNoteDialog() {
  if (!validateForm()) return;
  addNoteDialogOpen.value = true;
}

function saveNote(note: string) {
  const payload = buildPayload();
  if (note) payload.note = note;
  emit('submit', payload);
  reset();
}
</script>
<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;
.action-no-margin {
  padding: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  row-gap: 0.25rem;
  column-gap: 1rem;
  margin-bottom: 1rem;
}

.form-field {
  min-width: 0;
}

.form-field--full {
  grid-column: span 12;
}

.subclass-placeholder {
  width: 100%;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  border-radius: tokens.$field-border-radius;
  border: 1px solid rgba(0, 0, 0, 0.18);
  transition: border-color 0.36s cubic-bezier(0.4, 0, 0.2, 1);
  height: 2.5rem;
  background: linear-gradient(
    to bottom right,
    transparent 0%,
    transparent 49.5%,
    #e0e0e0 50.5%,
    #e0e0e0 100%
  );
  cursor: not-allowed;
}

@for $i from 1 through 12 {
  .form-field--span-#{$i} {
    grid-column: span #{$i};
  }
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-field {
    grid-column: span 1 !important;
  }
}
</style>
