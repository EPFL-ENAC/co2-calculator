<template>
  <q-card flat>
    <q-card-section class="q-pa-none">
      <q-form @submit.prevent="onSubmit">
        <div class="q-mx-lg q-my-xl">
          <div v-if="visibleFields.length === 0" class="text-subtle">
            No form configured
          </div>

          <div class="form-grid">
            <div
              v-for="inp in visibleFields"
              :key="inp.id"
              :class="['form-field', getGridClass(inp.ratio ?? inp?.ratio)]"
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
              <component
                :is="fieldComponent(inp.type)"
                v-else
                v-model="form[inp.id]"
                :label="
                  $t(`${inp.labelKey || inp.label}`, {
                    moduleTitle: $t(`${moduleType}-${submoduleType}`),
                  })
                "
                :placeholder="inp.placeholder"
                :type="inp.type === 'number' ? 'number' : undefined"
                :options="
                  dynamicOptions[inp.id] ??
                  inp.options?.map((o) => ({
                    label: o.label,
                    value: o.value,
                  })) ??
                  []
                "
                :loading="
                  (inp.id === 'class' && loadingClasses) ||
                  (inp.id === 'sub_class' && loadingSubclasses)
                "
                :error="!!errors[inp.id]"
                :error-message="errors[inp.id]"
                :min="inp.min"
                :max="inp.max"
                :dense="inp.type !== 'boolean' && inp.type !== 'checkbox'"
                :outlined="inp.type !== 'boolean' && inp.type !== 'checkbox'"
                :readonly="inp.id === 'act_power' || inp.id === 'pas_power'"
                :disable="inp.id === 'act_power' || inp.id === 'pas_power'"
                :color="inp.type === 'checkbox' ? 'accent' : undefined"
                :size="inp.type === 'checkbox' ? 'xs' : undefined"
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
              :label="$t('common_add_button')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium"
              type="submit"
            />
            <q-btn
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
import { QInput, QSelect, QCheckbox } from 'quasar';
import type { Component } from 'vue';
import { useI18n } from 'vue-i18n';
import { useModulePowerFactors } from 'src/composables/useModulePowerFactors';

const { t: $t } = useI18n();

interface Option {
  label: string;
  value: string;
}
type FieldValue = string | number | boolean | null | Option;
import type { Module } from 'src/constant/modules';

const props = defineProps<{
  fields?: ModuleField[] | null;
  rowData?: Record<string, FieldValue> | null;
  submoduleType?: 'scientific' | 'it' | 'other';
  moduleType: Module | string;
}>();

const visibleFields = computed(() =>
  (props.fields ?? []).filter((f) => !f.hideIn?.form),
);
const emit = defineEmits<{
  (e: 'submit', payload: Record<string, FieldValue>): void;
  (e: 'edit', payload: Record<string, FieldValue> | null): void;
}>();
const form = reactive<Record<string, FieldValue>>({});
const errors = reactive<Record<string, string | null>>({});
const { dynamicOptions, loadingClasses, loadingSubclasses } =
  useModulePowerFactors(form, toRef(props, 'submoduleType'));

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
// entirely in the useModulePowerFactors composable.
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
      switch (effectiveType) {
        case 'checkbox':
        case 'boolean':
          form[i.id] = false;
          break;
        case 'number':
          form[i.id] = null;
          break;
        default:
          form[i.id] = '';
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

function fieldComponent(type: string): Component {
  switch (type) {
    case 'select':
      return QSelect;
    case 'checkbox':
    case 'boolean':
      return QCheckbox;
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
    if (!validateField(i)) ok = false;
  });
  return ok;
}

function onSubmit() {
  if (!validateForm()) return;
  // Normalize payload types (numbers remain numbers, booleans kept, empty -> null/string)
  const payload: Record<string, string | number | boolean | null | Option> = {};
  Object.keys(form).forEach((k) => {
    const cfg = visibleFields.value.find((i) => i.id === k);
    const effectiveType = cfg?.type;
    const val = form[k];
    if (effectiveType === 'number') {
      payload[k] = val === null || val === '' ? null : Number(val);
    } else {
      payload[k] = val;
    }
  });
  emit('submit', payload);
  reset();
}

function reset() {
  visibleFields.value.forEach((i) => {
    const effectiveType = i.type;
    if (effectiveType === 'checkbox' || effectiveType === 'boolean')
      form[i.id] = false;
    else if (effectiveType === 'number') form[i.id] = null;
    else form[i.id] = '';
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
  //   border: 1px solid #999;
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
