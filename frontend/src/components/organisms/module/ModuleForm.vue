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
                  (inp.disableUntilField && !form[inp.disableUntilField]) ||
                  (inp.optionsId === 'subkind' &&
                    !loadingSubclasses &&
                    (filteredOptionsMap[inp.id]?.length ?? 0) === 0)
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
                          :model-value="
                            String(form[inp.id] || yearDateRange.default)
                          "
                          :default-view="form[inp.id] ? undefined : 'Calendar'"
                          :min="yearDateRange.min"
                          :max="yearDateRange.max"
                          :navigation-min-year-month="
                            yearDateRange.navigationMin
                          "
                          :navigation-max-year-month="
                            yearDateRange.navigationMax
                          "
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
                  :transport-mode="getTravelMode()"
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
              <template v-else-if="inp.type === 'headcount-member-select'">
                <HeadcountMemberSelect
                  :model-value="form[inp.id] ?? null"
                  :unit-id="props.unitId"
                  :year="props.year"
                  :label="
                    $t(`${inp.labelKey || inp.label}`, {
                      submoduleTitle: $t(`${moduleType}-${submoduleType}`),
                    })
                  "
                  :error="!!errors[inp.id]"
                  :error-message="errors[inp.id] ?? ''"
                  @update:model-value="(val) => (form[inp.id] = val)"
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
                :placeholder="inp.placeholder ? $t(inp.placeholder) : null"
                :hint="inp.hint ? $t(inp.hint) : null"
                :type="inp.type === 'number' ? 'number' : undefined"
                :options="getFilteredOptions(inp)"
                :loading="
                  inp.optionsId === 'kind'
                    ? loadingClasses
                    : inp.optionsId === 'subkind'
                      ? loadingSubclasses
                      : false
                "
                :error="!!errors[inp.id]"
                :error-message="errors[inp.id]"
                :min="inp.min"
                :max="inp.max"
                :step="inp.step"
                :dense="inp.type !== 'boolean' && inp.type !== 'checkbox'"
                :outlined="inp.type !== 'boolean' && inp.type !== 'checkbox'"
                :readonly="isReadOnly(inp)"
                :disable="inp.disable"
                :color="inp.type === 'checkbox' ? 'accent' : undefined"
                :size="inp.type === 'checkbox' ? 'xs' : undefined"
                :emit-value="inp.type === 'select'"
                :map-options="inp.type === 'select'"
              >
                <template v-if="inp.icon && inp.type !== 'checkbox'" #prepend>
                  <q-icon :name="inp.icon" color="grey-6" size="xs" />
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
import { reactive, watch, computed, ref, toRef } from 'vue';

import type { ModuleField } from 'src/constant/moduleConfig';
import { useWorkspaceStore } from 'src/stores/workspace';
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
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import DirectionInput from 'src/components/atoms/CO2DestinationInput.vue';
import NoteDialog from 'src/components/molecules/NoteDialog.vue';
import HeadcountMemberSelect from 'src/components/organisms/module/HeadcountMemberSelect.vue';
import { calculateDistance } from 'src/api/locations';
import { useEquipmentClassOptions } from 'src/composables/useEquipmentClassOptions';
import { useBuildingRoomDynamicOptions } from 'src/composables/useBuildingRoomDynamicOptions';
import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  SUBMODULE_PROFESSIONAL_TRAVEL_TYPES,
} from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';

const { t: $t } = useI18n();
const workspaceStore = useWorkspaceStore();
const moduleStore = useModuleStore();

const addNoteDialogOpen = ref(false);

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
    hasAddWithNote: true,
    addButtonLabelKey: 'common_add_button',
    unitId: undefined,
    year: undefined,
  },
);

const selectedYear = computed(
  () => workspaceStore.selectedYear ?? new Date().getFullYear(),
);

const yearDateRange = computed(() => ({
  min: `${selectedYear.value}/01/01`,
  max: `${selectedYear.value}/12/31`,
  navigationMin: `${selectedYear.value}/01`,
  navigationMax: `${selectedYear.value}/12`,
  default: `${selectedYear.value}/01/01`,
}));

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

function isReadOnly(inp: ModuleField): boolean {
  if (inp.disable || inp.readOnly) return true;
  if (!inp.readOnlyWhenFilled) return false;

  const value = form[inp.id];
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim() !== '';
  return true;
}

// Generic conditional options filtering - made reactive with computed
const filteredOptionsMap = computed(() => {
  const map: Record<string, Array<{ value: string; label: string }>> = {};

  visibleFields.value.forEach((inp) => {
    // First check for dynamic options (from composables)
    // For Buildings > Building submodule, prefer room-based options over factor-based ones
    const optionsId = inp?.optionsId ?? '';
    const buildingRoomOpts =
      props.moduleType === MODULES.Buildings &&
      props.submoduleType === SUBMODULE_BUILDINGS_TYPES.Building &&
      buildingRoomDynamicOptions[optionsId]?.length > 0
        ? buildingRoomDynamicOptions[optionsId]
        : undefined;
    const dynamicOpts = buildingRoomOpts ?? dynamicOptions[optionsId];
    const baseOptions =
      dynamicOpts && dynamicOpts.length > 0
        ? dynamicOpts
        : (inp.options?.map((o) => ({
            label: $t(o.label) !== o.label ? $t(o.label) : o.label,
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
  const taxoNode =
    moduleStore.state.taxonomySubmodule[props.submoduleType ?? ''];
  const opts = filteredOptionsMap.value[inp.id] ?? [];
  opts.forEach((opt) => {
    const taxoOptNode = taxoNode?.children?.find(
      (node) => node.name === opt.value,
    );
    if (taxoOptNode) {
      opt.label = taxoOptNode.label;
    }
  });
  return opts;
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

const kindFieldId = computed(() => {
  const kindField = visibleFields.value.find((f) => f.optionsId === 'kind');
  return kindField ? kindField.id : null;
});

const subkindFieldId = computed(() => {
  const subkindField = visibleFields.value.find(
    (f) => f.optionsId === 'subkind',
  );
  return subkindField ? subkindField.id : null;
});

const useEquipmentClassOptionsConfig: Record<string, string> = {};
if (props.moduleType === MODULES.EquipmentElectricConsumption) {
  useEquipmentClassOptionsConfig['primaryValueFieldId'] = 'active_power_w';
  useEquipmentClassOptionsConfig['secondaryValueFieldId'] = 'standby_power_w';
} else if (
  props.moduleType === MODULES.Buildings &&
  props.submoduleType === SUBMODULE_BUILDINGS_TYPES.EnergyCombustion
) {
  useEquipmentClassOptionsConfig['primaryValueFieldId'] = 'unit';
}

const { dynamicOptions, loadingClasses, loadingSubclasses } =
  useEquipmentClassOptions(form, toRef(props, 'submoduleType'), {
    classFieldId: kindFieldId.value ?? undefined,
    subClassFieldId: subkindFieldId.value ?? undefined,
    fetchFactorValuesOnChange: true,
    ...useEquipmentClassOptionsConfig,
  });

const { dynamicOptions: buildingRoomDynamicOptions } =
  useBuildingRoomDynamicOptions(
    form,
    toRef(props, 'moduleType'),
    toRef(props, 'submoduleType'),
  );

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

function init() {
  if (props.rowData) {
    Object.keys(props.rowData).forEach((key) => {
      form[key] = props.rowData[key];
      errors[key] = null;
    });
    // Pre-populate DirectionInput display text from the identifier fields
    form.origin =
      (props.rowData.origin_iata as string) ||
      (props.rowData.origin_name as string) ||
      '';
    form.destination =
      (props.rowData.destination_iata as string) ||
      (props.rowData.destination_name as string) ||
      '';
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
                i.options?.map((o) => ({
                  label: o.label,
                  value: o.value,
                })) ?? [];
              return options.length > 0 ? options[0].value : '';
            })();
            break;
          case 'direction-input':
            // Initialize origin and destination fields separately
            if (!form.origin) form.origin = '';
            if (!form.destination) form.destination = '';
            // Location IDs — only for distance preview, NOT sent to backend
            if (!props.rowData) {
              form.origin_location_id = undefined;
              form.destination_location_id = undefined;
              // Identifier fields sent to backend
              form.origin_iata = undefined;
              form.destination_iata = undefined;
              form.origin_name = undefined;
              form.destination_name = undefined;
            }
            break;
          default:
            // Use null for select/headcount-member-select, empty string for text
            form[i.id] =
              effectiveType === 'select' ||
              effectiveType === 'headcount-member-select'
                ? null
                : '';
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

// Watch for changes to location IDs and number of trips to calculate distance.
watch(
  () => [
    form.origin_location_id,
    form.destination_location_id,
    form.number_of_trips,
  ],
  async () => {
    const travelMode = getTravelMode();
    if (!travelMode) return;
    if (
      form.origin_location_id === undefined ||
      form.origin_location_id === null ||
      form.destination_location_id === undefined ||
      form.destination_location_id === null
    ) {
      form.distance_km = null;
      return;
    }
    form.distance_km = await calculateDistance(
      form.origin_location_id as number,
      form.destination_location_id as number,
      travelMode,
      (form.number_of_trips as number) || 1,
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

  if (
    i.id === 'active_usage_hours_per_week' ||
    i.id === 'standby_usage_hours_per_week'
  ) {
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

  // Skip validation for subkind fields with no available options (class has no sub-classes)
  if (
    i.optionsId === 'subkind' &&
    (filteredOptionsMap.value[i.id]?.length ?? 0) === 0
  ) {
    return true;
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
    'origin_location_id',
    'destination_location_id',
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

  return payload;
}

function setFieldError(fieldId: string, error: string | null) {
  errors[fieldId] = error;
}

defineExpose({ setFieldError });

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
    else if (effectiveType === 'radio-group') {
      // Set first option as default
      const options =
        i.options?.map((o) => ({
          label: o.label,
          value: o.value,
        })) ?? [];
      form[i.id] = options.length > 0 ? options[0].value : '';
    } else if (effectiveType === 'direction-input') {
      // Clear origin and destination fields
      form.origin = '';
      form.destination = '';
      // Reset location IDs and identifier fields
      form.origin_location_id = undefined;
      form.destination_location_id = undefined;
      form.distance_km = null;
      form.origin_iata = undefined;
      form.destination_iata = undefined;
      form.origin_name = undefined;
      form.destination_name = undefined;
    } else {
      // Use null for select/headcount-member-select, empty string for text
      form[i.id] =
        effectiveType === 'select' ||
        effectiveType === 'headcount-member-select'
          ? null
          : '';
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

async function handleFromLocationSelected(location: {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  iata_code: string | null;
  country_code: string | null;
}) {
  const travelMode = getTravelMode();
  if (!travelMode) return;

  form.origin_location_id = location.id;

  // Store the correct identifier for the backend payload
  if (travelMode === 'plane') {
    form.origin_iata = location.iata_code ?? location.name;
  } else {
    form.origin_name = location.name;
  }

  if (
    form.destination_location_id === undefined ||
    form.destination_location_id === null
  ) {
    form.distance_km = null;
    return;
  }
  form.distance_km = await calculateDistance(
    form.origin_location_id as number,
    form.destination_location_id as number,
    travelMode,
    (form.number_of_trips as number) || 1,
  );
}

async function handleToLocationSelected(location: {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  iata_code: string | null;
  country_code: string | null;
}) {
  const travelMode = getTravelMode();
  if (!travelMode) return;
  form.destination_location_id = location.id;

  // Store the correct identifier for the backend payload
  if (travelMode === 'plane') {
    form.destination_iata = location.iata_code ?? location.name;
  } else {
    form.destination_name = location.name;
  }

  if (
    form.origin_location_id === undefined ||
    form.origin_location_id === null
  ) {
    form.distance_km = null;
    return;
  }
  form.distance_km = await calculateDistance(
    form.origin_location_id as number,
    form.destination_location_id as number,
    travelMode,
    (form.number_of_trips as number) || 1,
  );
}

async function handleSwapLocations() {
  const travelMode = getTravelMode();
  if (!travelMode) return;
  // Swap location IDs when user swaps from/to
  const oldOriginId = form.origin_location_id;
  const oldDestinationId = form.destination_location_id;

  form.origin_location_id = oldDestinationId;
  form.destination_location_id = oldOriginId;

  // Swap identifiers
  if (travelMode === 'plane') {
    [form.origin_iata, form.destination_iata] = [
      form.destination_iata,
      form.origin_iata,
    ];
  } else {
    [form.origin_name, form.destination_name] = [
      form.destination_name,
      form.origin_name,
    ];
  }

  if (
    form.origin_location_id === undefined ||
    form.origin_location_id === null ||
    form.destination_location_id === undefined ||
    form.destination_location_id === null
  ) {
    form.distance_km = null;
    return;
  }
  form.distance_km = await calculateDistance(
    form.origin_location_id as number,
    form.destination_location_id as number,
    travelMode,
    (form.number_of_trips as number) || 1,
  );
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
