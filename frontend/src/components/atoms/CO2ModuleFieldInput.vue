<template>
  <div>
    <q-select
      v-if="field.type === 'select'"
      v-model="formModel"
      :label="label"
      :placeholder="field.placeholder ? $t(field.placeholder) : null"
      :hint="field.hint ? $t(field.hint) : null"
      :options="options"
      :min="field.min"
      :max="field.max"
      :step="field.step"
      :dense="true"
      :outlined="true"
      :readonly="isFieldReadOnly"
      :disable="disabled"
      emit-value
      map-options
      :error="!!errors"
      :error-message="errors"
    />
    <q-checkbox
      v-else-if="field.type === 'checkbox' || field.type === 'boolean'"
      v-model="formModel"
      :label="label"
      :hint="field.hint ? $t(field.hint) : null"
      :readonly="isFieldReadOnly"
      :disable="disabled"
      color="accent"
      size="xs"
      :error="!!errors"
      :error-message="errors"
    />
    <q-input
      v-else
      v-model="formModel"
      :label="label"
      :placeholder="field.placeholder ? $t(field.placeholder) : null"
      :hint="field.hint ? $t(field.hint) : null"
      :type="field.type === 'number' ? 'number' : undefined"
      :min="field.min"
      :max="field.max"
      :step="field.step"
      :dense="true"
      :outlined="true"
      :readonly="isFieldReadOnly"
      :disable="disabled"
      :error="!!errors"
      :error-message="errors"
    >
      <template v-if="field.icon" #prepend>
        <q-icon :name="field.icon" color="grey-6" size="xs" />
      </template>
    </q-input>
  </div>
</template>

<script lang="ts" setup>
import { computed } from 'vue';
import type { ModuleField } from 'src/constant/moduleConfig';
import type { AllSubmoduleTypes, Module } from 'src/constant/modules';
import { useI18n } from 'vue-i18n';

const { t: $t } = useI18n();

const props = defineProps<{
  modelValue: string | number | undefined | null;
  moduleType: Module | string;
  submoduleType: AllSubmoduleTypes;
  field: ModuleField;
  entry: Record<string, unknown>;
  loading?: boolean;
  errors?: string | null | undefined;
  disabled?: boolean;
  options?: Array<{ value: string; label: string }>;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number | null): void;
}>();

const formModel = computed({
  get() {
    return props.modelValue;
  },
  set(value: string | number | null) {
    emit('update:modelValue', value);
  },
});

const label = computed(() =>
  $t(`${props.field.labelKey || props.field.label}`, {
    submoduleTitle: $t(`${props.moduleType}-${props.submoduleType}`),
  }),
);

const isFieldReadOnly = computed(() => {
  if (props.disabled || props.field.readOnly) return true;
  if (
    props.field.readOnlyWhenFilled &&
    props.modelValue !== null &&
    props.modelValue !== undefined &&
    props.modelValue !== ''
  ) {
    return true;
  }
  return false;
});
</script>
