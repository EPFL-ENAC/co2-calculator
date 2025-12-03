<template>
  <q-card flat>
    <q-card-section class="q-pa-none">
      <q-form @submit.prevent="onSubmit">
        <div class="q-mx-lg q-my-xl">
          <div v-if="!inputs || inputs.length === 0" class="text-subtle">
            No form configured
          </div>

          <div class="form-grid">
            <div
              v-for="inp in inputs ?? []"
              :key="inp.id"
              :class="['form-field', getGridClass(inp.ratio)]"
            >
              <component
                :is="fieldComponent(inp.type)"
                v-model="form[inp.id]"
                :label="inp.label"
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
                  (inp.id === 'sci_class' && loadingClasses) ||
                  (inp.id === 'sci_sub_class' && loadingSubclasses)
                "
                :error="!!errors[inp.id]"
                :error-message="errors[inp.id]"
                :min="inp.min"
                :max="inp.max"
                :dense="inp.type !== 'boolean' && inp.type !== 'checkbox'"
                :outlined="inp.type !== 'boolean' && inp.type !== 'checkbox'"
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
import { reactive, watch, ref } from 'vue';
import type { FormInput } from 'src/constant/moduleConfig';
import { QInput, QSelect, QCheckbox } from 'quasar';
import type { Component } from 'vue';
import { useI18n } from 'vue-i18n';

const { t: $t } = useI18n();

type FieldValue = string | number | boolean | null | Option;
import { usePowerFactorsStore } from 'src/stores/powerFactors';

const props = defineProps<{
  inputs?: FormInput[] | null;
  rowData?: Record<string, FieldValue> | null;
  submoduleKey?: 'scientific' | 'it' | 'other';
}>();
const emit = defineEmits<{
  (
    e: 'submit',
    payload: Record<string, string | number | boolean | null | Option>,
  ): void;
  (e: 'edit', payload: Record<string, FieldValue> | null): void;
}>();
const form = reactive<Record<string, FieldValue>>({});
const errors = reactive<Record<string, string | null>>({});
const dynamicOptions = reactive<
  Record<string, { label: string; value: string }[]>
>({});
const loadingClasses = ref(false);
const loadingSubclasses = ref(false);

async function loadClassOptions() {
  if (!props.submoduleKey) return;
  loadingClasses.value = true;
  try {
    const store = usePowerFactorsStore();
    dynamicOptions['sci_class'] = await store.fetchClassOptions(
      props.submoduleKey,
    );
  } catch {
    dynamicOptions['sci_class'] = [];
  } finally {
    loadingClasses.value = false;
  }
}

interface Option {
  label: string;
  value: string;
}

async function loadSubclassOptions(selectedClass: Option | null) {
  if (!props.submoduleKey || !selectedClass) {
    dynamicOptions['sci_sub_class'] = [];
    return;
  }
  loadingSubclasses.value = true;
  try {
    const store = usePowerFactorsStore();
    dynamicOptions['sci_sub_class'] = await store.fetchSubclassOptions(
      props.submoduleKey,
      selectedClass.value,
    );
  } catch {
    dynamicOptions['sci_sub_class'] = [];
  } finally {
    loadingSubclasses.value = false;
  }
}

function init() {
  if (props.rowData) {
    Object.keys(props.rowData).forEach((key) => {
      form[key] = props.rowData[key];
      errors[key] = null;
    });
    return;
  }
  (props.inputs ?? []).forEach((i) => {
    if (props.rowData && props.rowData[i.id] !== undefined) {
      // Edit mode: populate from rowData
      form[i.id] = props.rowData[i.id];
    } else {
      // Add mode: initialize with defaults
      switch (i.type) {
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
  () => [props.inputs, props.rowData],
  () => init(),
  { deep: true, immediate: true },
);

watch(
  () => props.submoduleKey,
  async () => {
    await loadClassOptions();
    if ('sci_sub_class' in form) form['sci_sub_class'] = '';
    dynamicOptions['sci_sub_class'] = [];
  },
  { immediate: true },
);

watch(
  () => form['sci_class'] as Option | null,
  async (val) => {
    await loadSubclassOptions(val);
    if ('sci_sub_class' in form) form['sci_sub_class'] = '';
  },
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

function validateField(i: FormInput) {
  const v = form[i.id];
  errors[i.id] = null;
  if (i.required) {
    if (i.type === 'checkbox' || i.type === 'boolean') {
      if (!v) errors[i.id] = 'Required';
    } else if (v === '' || v === null || v === undefined) {
      errors[i.id] = 'Required';
    }
  }
  if (i.type === 'number' && v !== '' && v !== null && v !== undefined) {
    const n = Number(v);
    if (Number.isNaN(n)) errors[i.id] = 'Must be a number';
    if (i.min !== undefined && n < i.min) errors[i.id] = `Min ${i.min}`;
    if (i.max !== undefined && n > i.max) errors[i.id] = `Max ${i.max}`;
  }
  return !errors[i.id];
}

function validateForm() {
  let ok = true;
  (props.inputs ?? []).forEach((i) => {
    if (!validateField(i)) ok = false;
  });
  return ok;
}

function onSubmit() {
  if (!validateForm()) return;
  // Normalize payload types (numbers remain numbers, booleans kept, empty -> null/string)
  const payload: Record<string, string | number | boolean | null | Option> = {};
  Object.keys(form).forEach((k) => {
    const cfg = (props.inputs ?? []).find((i) => i.id === k);
    const val = form[k];
    if (cfg?.type === 'number') {
      payload[k] = val === null || val === '' ? null : Number(val);
    } else {
      payload[k] = val;
    }
  });
  emit('submit', payload);
  reset();
}

function reset() {
  (props.inputs ?? []).forEach((i) => {
    if (i.type === 'checkbox' || i.type === 'boolean') form[i.id] = false;
    else if (i.type === 'number') form[i.id] = null;
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
