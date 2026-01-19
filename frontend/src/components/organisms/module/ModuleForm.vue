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
              <template
                v-if="
                  inp.id === 'sub_class' &&
                  !loadingSubclasses &&
                  (!dynamicOptions['sub_class'] ||
                    dynamicOptions['sub_class'].length === 0) &&
                  !form['sub_class']
                "
              >
                <div class="subclass-placeholder" />
              </template>
              <template v-else-if="inp.type === 'radio-group'">
                <div class="radio-group-field q-mb-sm">
                  <q-radio
                    v-for="option in getFilteredOptions(inp)"
                    :key="option.value"
                    v-model="form[inp.id]"
                    :val="option.value"
                    :label="option.label"
                    :disable="inp.disable"
                    color="accent"
                  />

                  <div
                    v-if="errors[inp.id]"
                    class="text-negative text-caption q-mt-xs"
                  >
                    {{ errors[inp.id] }}
                  </div>
                </div>
              </template>
              <template v-else-if="inp.type === 'date'">
                <q-input
                  :model-value="String(form[inp.id] || '')"
                  bordered
                  mask="####/##/##"
                  :rules="getDateRules(inp.required)"
                  :label="
                    $t(`${inp.labelKey || inp.label}`, {
                      submoduleTitle: $t(`${moduleType}-${submoduleType}`),
                    })
                  "
                  :error="!!errors[inp.id]"
                  :error-message="errors[inp.id]"
                  :required="inp.required"
                  :dense="true"
                  :outlined="true"
                  :disable="inp.disable"
                  @update:model-value="
                    (val) => (form[inp.id] = val as FieldValue)
                  "
                >
                  <template #append>
                    <q-icon name="o_event" class="cursor-pointer">
                      <q-popup-proxy
                        cover
                        transition-show="scale"
                        transition-hide="scale"
                      >
                        <q-date
                          :model-value="String(form[inp.id] || '')"
                          :min="currentYearMinDate"
                          :max="currentYearMaxDate"
                          @update:model-value="
                            (val) => (form[inp.id] = val as FieldValue)
                          "
                        >
                          <div class="row items-center justify-end">
                            <q-btn
                              v-close-popup
                              label="Close"
                              color="primary"
                              flat
                            />
                          </div>
                        </q-date>
                      </q-popup-proxy>
                    </q-icon>
                  </template>
                </q-input>
              </template>
              <template v-else-if="inp.type === 'direction-input'">
                <DirectionInput
                  :from="String(form.origin ?? '')"
                  :to="String(form.destination ?? '')"
                  :error="!!errors.origin || !!errors.destination"
                  :error-message="errors.origin || errors.destination || ''"
                  :transport-mode="
                    !rowData && form.transport_mode
                      ? (form.transport_mode as 'flight' | 'train')
                      : undefined
                  "
                  :disable="inp.disable"
                  @update:from="
                    (val) => {
                      form.origin = val;
                    }
                  "
                  @update:to="
                    (val) => {
                      form.destination = val;
                    }
                  "
                  @from-location-selected="handleFromLocationSelected"
                  @to-location-selected="handleToLocationSelected"
                  @swap="handleSwapLocations"
                />
              </template>
              <component
                :is="fieldComponent(inp.type)"
                v-else
                v-model="form[inp.id]"
                :label="
                  $t(`${inp.labelKey || inp.label}`, {
                    submoduleTitle: $t(`${moduleType}-${submoduleType}`),
                  })
                "
                :placeholder="inp.placeholder"
                :type="inp.type === 'number' ? 'number' : undefined"
                :options="getFilteredOptions(inp)"
                :loading="
                  (inp.id === 'class' && loadingClasses) ||
                  (inp.id === 'sub_class' && loadingSubclasses)
                "
                :error="!!errors[inp.id]"
                :error-message="errors[inp.id]"
                :min="inp.min"
                :max="inp.max"
                :step="inp.step"
                :dense="inp.type !== 'boolean' && inp.type !== 'checkbox'"
                :outlined="inp.type !== 'boolean' && inp.type !== 'checkbox'"
                :readonly="inp.disable"
                :disable="inp.disable"
                :color="inp.type === 'checkbox' ? 'accent' : undefined"
                :size="inp.type === 'checkbox' ? 'xs' : undefined"
                :emit-value="inp.type === 'select'"
                :map-options="inp.type === 'select'"
              >
                <template v-if="inp.icon && inp.type !== 'checkbox'" #prepend>
                  <q-icon :name="inp.icon" color="grey-6" size="xs" />
                </template>
                <template v-if="inp.type === 'select'" #hint>
                  <div class="text-subtle">Select a value</div>
                </template>
              </component>
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
              disabled
              icon="o_add_comment"
              color="primary"
              :label="$t('common_add_with_note_button')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium q-mr-sm"
            />
          </template>
        </q-card-actions>
      </q-form>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { reactive, watch, computed, toRef } from 'vue';

import type { ModuleField } from 'src/constant/moduleConfig';
import {
  QInput,
  QSelect,
  QCheckbox,
  QRadio,
  QDate,
  QPopupProxy,
  QIcon,
} from 'quasar';
import type { Component } from 'vue';
import { useI18n } from 'vue-i18n';
import { useEquipmentClassOptions } from 'src/composables/useEquipmentClassOptions';
import StudentFTECalculator from './StudentFTECalculator.vue';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import DirectionInput from 'src/components/atoms/CO2DestinationInput.vue';
import { calculateDistance } from 'src/api/locations';
import { MODULES } from 'src/constant/modules';

const { t: $t } = useI18n();

interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
import type { AllSubmoduleTypes, Module } from 'src/constant/modules';

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
    unitId?: string;
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

// Compute current year date range to restrict date picker
const currentYearMinDate = computed(() => {
  const currentYear = new Date().getFullYear();
  return `${currentYear}/01/01`;
});

const currentYearMaxDate = computed(() => {
  const currentYear = new Date().getFullYear();
  return `${currentYear}/12/31`;
});

const visibleFields = computed(() =>
  (props.fields ?? []).filter((f) => !f.hideIn?.form),
);

// Generic conditional visibility handling
const visibleFieldsWithConditional = computed(() => {
  return visibleFields.value.filter((f) => {
    if (!f.conditionalVisibility) return true;

    const { showWhen, hideWhen } = f.conditionalVisibility;

    // Check showWhen condition
    if (showWhen) {
      const fieldValue = form[showWhen.fieldId];
      if (fieldValue !== showWhen.value) {
        return false;
      }
    }

    // Check hideWhen condition
    if (hideWhen) {
      const fieldValue = form[hideWhen.fieldId];
      if (fieldValue === hideWhen.value) {
        return false;
      }
    }

    return true;
  });
});

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

// Generic conditional options filtering - made reactive with computed
const filteredOptionsMap = computed(() => {
  const map: Record<string, Array<{ value: string; label: string }>> = {};

  visibleFields.value.forEach((inp) => {
    // First check for dynamic options (from composables)
    // Use dynamic options if they exist and are not empty, otherwise use static options
    const dynamicOpts = dynamicOptions[inp.id];
    const baseOptions =
      dynamicOpts && dynamicOpts.length > 0
        ? dynamicOpts
        : (inp.options?.map((o) => ({
            label: o.label,
            value: o.value,
          })) ?? []);

    // If no conditionalOptions, return base options
    if (!inp.conditionalOptions) {
      map[inp.id] = baseOptions;
      return;
    }

    // Handle both single condition and array of conditions
    const conditions = Array.isArray(inp.conditionalOptions)
      ? inp.conditionalOptions
      : [inp.conditionalOptions];

    // Check each condition - first match wins
    let matched = false;
    for (const condition of conditions) {
      const { when, showOptions } = condition;
      const fieldValue = form[when.fieldId];

      // If condition matches, filter to only show specified options
      if (fieldValue === when.value) {
        map[inp.id] = baseOptions.filter((opt) =>
          showOptions.includes(opt.value),
        );
        matched = true;
        break;
      }
    }

    // If no condition matches, show all options
    if (!matched) {
      map[inp.id] = baseOptions;
    }
  });

  return map;
});

function getFilteredOptions(
  inp: ModuleField,
): Array<{ value: string; label: string }> {
  return filteredOptionsMap.value[inp.id] ?? [];
}

function getDateRules(required?: boolean) {
  const dateFormatRule = (val: string) => {
    if (!val || val === '') return required ? 'Required' : true;
    return /^\d{4}[/.]\d{2}[/.]\d{2}$/.test(val) || 'Invalid date format';
  };
  return [dateFormatRule];
}
const emit = defineEmits<{
  (e: 'submit', payload: Record<string, FieldValue>): void;
  (e: 'edit', payload: Record<string, FieldValue> | null): void;
}>();
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const form = reactive<Record<string, any>>({});
const errors = reactive<Record<string, string | null>>({});
const {
  dynamicOptions: equipmentOptions,
  loadingClasses,
  loadingSubclasses,
} = useEquipmentClassOptions(form, toRef(props, 'submoduleType'));

// Use equipment options directly as dynamic options
const dynamicOptions = equipmentOptions;

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

// legacy helpers kept only for typing compatibility; logic lives
// entirely in the useEquipmentClassOptions composable.
// They are intentionally not used here.

function init() {
  if (props.rowData) {
    Object.keys(props.rowData).forEach((key) => {
      form[key] = props.rowData[key];
      errors[key] = null;
    });
    return;
  }
  visibleFields.value.forEach((i) => {
    const effectiveType = i.type;
    if (props.rowData && props.rowData[i.id] !== undefined) {
      form[i.id] = props.rowData[i.id];
    } else {
      // Check if field has a default value
      if (i.default !== undefined) {
        form[i.id] = i.default;
      } else {
        switch (effectiveType) {
          case 'checkbox':
          case 'boolean':
            form[i.id] = false;
            break;
          case 'number':
            form[i.id] = null;
            break;
          case 'radio-group':
            form[i.id] = (() => {
              const options =
                dynamicOptions[i.id] ??
                i.options?.map((o) => ({
                  label: o.label,
                  value: o.value,
                })) ??
                [];
              return options.length > 0 ? options[0].value : '';
            })();
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
  });
}

// re-init when inputs or rowData change (e.g. dynamic config or edit mode)
watch(
  () => [props.fields, props.rowData],
  () => init(),
  { deep: true, immediate: true },
);

// When conditionalOptions dependencies change, reset dependent fields if their value is invalid
watch(
  () => filteredOptionsMap.value,
  (newOptionsMap) => {
    visibleFields.value.forEach((field) => {
      if (!field.conditionalOptions) return;

      const currentValue = form[field.id];
      if (
        currentValue === null ||
        currentValue === undefined ||
        currentValue === ''
      )
        return;

      const validOptions = newOptionsMap[field.id] || [];
      const isValid = validOptions.some((opt) => opt.value === currentValue);

      if (!isValid) {
        form[field.id] = null;
      }
    });
  },
);

// Clear location data when transport mode changes (specific to professional travel)
watch(
  () => form.transport_mode,
  (newMode, oldMode) => {
    // Only clear if transport mode actually changed (not on initial mount)
    if (oldMode !== undefined && newMode !== oldMode && !props.rowData) {
      // Clear origin and destination field values
      form.origin = '';
      form.destination = '';
      // Clear location IDs when switching transport modes
      form.origin_location_id = undefined;
      form.destination_location_id = undefined;
      // Clear distance when transport mode changes
      form.distance_km = null;
    }
  },
);

// Watch for changes to location IDs and transport mode to calculate distance
watch(
  () => [
    form.origin_location_id,
    form.destination_location_id,
    form.transport_mode,
  ],
  () => {
    form.distance_km = calculateDistance(
      form.origin_location_id as number,
      form.destination_location_id as number,
      form.transport_mode as 'flight' | 'train',
    );
  },
);

function fieldComponent(type: string): Component {
  switch (type) {
    case 'select':
      return QSelect;
    case 'checkbox':
    case 'boolean':
      return QCheckbox;
    case 'radio-group':
      // Radio groups are handled in template, not here
      return QInput;
    default:
      return QInput;
  }
}

function validateField(i: ModuleField) {
  const v = form[i.id];
  const effectiveType = i.type;
  errors[i.id] = null;

  if (i.id === 'act_usage' || i.id === 'pas_usage') {
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

function onSubmit() {
  if (!validateForm()) {
    return;
  }
  // Normalize payload types (numbers remain numbers, booleans kept, empty -> null/string)
  const payload: Record<string, string | number | boolean | null | Option> = {};

  // Fields to exclude from submission (read-only display fields)
  const excludedFields = [
    'origin_location_data',
    'destination_location_data',
    'origin', // Display-only field for table
    'destination', // Display-only field for table
    'round_trip', // Direction input field (not backend field)
    'distance_km', // Read-only calculated field
    'kg_co2eq', // Read-only calculated field
  ];

  Object.keys(form).forEach((k) => {
    // Skip excluded fields
    if (excludedFields.includes(k)) {
      return;
    }

    const cfg = visibleFields.value.find((i) => i.id === k);
    const effectiveType = cfg?.type;
    const val = form[k];

    if (effectiveType === 'number') {
      payload[k] = val === null || val === '' ? null : Number(val);
    } else {
      payload[k] = val as FieldValue;
    }
  });

  // Include location IDs for professional travel when creating new entries
  // Only include if we have location IDs (from autocomplete selection)
  if (
    !props.rowData &&
    form.origin_location_id !== undefined &&
    form.destination_location_id !== undefined
  ) {
    payload.origin_location_id = form.origin_location_id as number;
    payload.destination_location_id = form.destination_location_id as number;
  }

  // Backend expects 'class_' (with underscore) for Python compatibility
  // Rename 'class' to 'class_' before sending to backend
  if ('class' in payload) {
    payload.class_ = payload.class;
    delete payload.class;
  }

  emit('submit', payload);
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
    else if (effectiveType === 'radio-group') {
      // Set first option as default
      const options =
        dynamicOptions[i.id] ??
        i.options?.map((o) => ({
          label: o.label,
          value: o.value,
        })) ??
        [];
      form[i.id] = options.length > 0 ? options[0].value : '';
    } else if (effectiveType === 'direction-input') {
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

async function handleFromLocationSelected(location: {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
}) {
  form.origin_location_id = location.id;
  form.distance_km = await calculateDistance(
    form.origin_location_id as number,
    form.destination_location_id as number,
    form.transport_mode as 'flight' | 'train',
  );
}

async function handleToLocationSelected(location: {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
}) {
  form.destination_location_id = location.id;
  form.distance_km = await calculateDistance(
    form.origin_location_id as number,
    form.destination_location_id as number,
    form.transport_mode as 'flight' | 'train',
  );
}

async function handleSwapLocations() {
  // Swap location IDs when user swaps from/to
  const oldOriginId = form.origin_location_id;
  const oldDestinationId = form.destination_location_id;

  form.origin_location_id = oldDestinationId;
  form.destination_location_id = oldOriginId;
  form.distance_km = await calculateDistance(
    form.origin_location_id as number,
    form.destination_location_id as number,
    form.transport_mode as 'flight' | 'train',
  );
}

function clearOriginAndDestination() {
  // Clear origin and destination fields when add button is clicked
  // This ensures fields are cleared after successful form submission
  // The reset() function will handle the actual clearing
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
