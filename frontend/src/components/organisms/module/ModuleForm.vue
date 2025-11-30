<template>
  <q-card>
    <q-card-section>
      <q-form @submit.prevent="onSubmit">
        <div v-if="!inputs || inputs.length === 0" class="text-subtle">
          No form configured
        </div>

        <div v-for="inp in inputs ?? []" :key="inp.id" class="q-mb-md">
          <component
            :is="fieldComponent(inp.type)"
            v-model="form[inp.id]"
            :label="inp.label"
            :placeholder="inp.placeholder"
            :type="inp.type === 'number' ? 'number' : undefined"
            :options="
              inp.options?.map((o) => ({ label: o.label, value: o.value }))
            "
            :error="!!errors[inp.id]"
            :error-message="errors[inp.id]"
            :min="inp.min"
            :max="inp.max"
            dense
            hide-bottom-space
            style="max-width: 720px"
          >
            <template v-if="inp.type === 'select'" #hint>
              <div class="text-subtle">Select a value</div>
            </template>
          </component>
        </div>

        <q-card-actions align="right">
          <q-btn flat label="Reset" @click="reset" />
          <q-btn color="primary" label="Submit" type="submit" />
        </q-card-actions>
      </q-form>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue';
import type { FormInput } from 'src/constant/moduleConfig';
import { QInput, QSelect, QCheckbox } from 'quasar';
import type { Component } from 'vue';

const props = defineProps<{
  inputs?: FormInput[] | null;
}>();
const emit = defineEmits<{
  (
    e: 'submit',
    payload: Record<string, string | number | boolean | null>,
  ): void;
}>();

type FieldValue = string | number | boolean | null;
const form = reactive<Record<string, FieldValue>>({});
const errors = reactive<Record<string, string | null>>({});

function init() {
  (props.inputs ?? []).forEach((i) => {
    switch (i.type) {
      case 'checkbox':
        form[i.id] = false;
        break;
      case 'number':
        form[i.id] = null;
        break;
      default:
        form[i.id] = '';
    }
    errors[i.id] = null;
  });
}
init();

// re-init when inputs change (e.g. dynamic config)
watch(
  () => props.inputs,
  () => init(),
  { deep: true },
);

function fieldComponent(type: string): Component {
  switch (type) {
    case 'select':
      return QSelect;
    case 'checkbox':
      return QCheckbox;
    default:
      return QInput;
  }
}

function validateField(i: FormInput) {
  const v = form[i.id];
  errors[i.id] = null;
  if (i.required) {
    if (i.type === 'checkbox') {
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
  const payload: Record<string, string | number | boolean | null> = {};
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
    if (i.type === 'checkbox') form[i.id] = false;
    else if (i.type === 'number') form[i.id] = null;
    else form[i.id] = '';
    errors[i.id] = null;
  });
}
</script>
<style scoped></style>
