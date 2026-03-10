<template>
  <component
    :is="fieldComponent(field.type)"
    v-model="formModel"
    :label="label"
    :placeholder="field.placeholder ? $t(field.placeholder) : null"
    :hint="field.hint ? $t(field.hint) : null"
    :type="field.type === 'number' ? 'number' : undefined"
    :options="fieldOptions"
    :min="field.min"
    :max="field.max"
    :step="field.step"
    :dense="field.type !== 'boolean' && field.type !== 'checkbox'"
    :outlined="field.type !== 'boolean' && field.type !== 'checkbox'"
    :readonly="isFieldReadOnly"
    :disable="fieldDisabled"
    :color="field.type === 'checkbox' ? 'accent' : undefined"
    :size="field.type === 'checkbox' ? 'xs' : undefined"
    :emit-value="field.type === 'select'"
    :map-options="field.type === 'select'"
    :error="!!errors"
    :error-message="errors"
  >
    <template v-if="field.icon && field.type !== 'checkbox'" #prepend>
      <q-icon :name="field.icon" color="grey-6" size="xs" />
    </template>
  </component>
</template>

<script lang="ts" setup>
import type { Component } from 'vue';
import { computed, ref, watchEffect } from 'vue';
import { QInput, QSelect, QCheckbox, QIcon } from 'quasar';
import type { ModuleField } from 'src/constant/moduleConfig';
import type { AllSubmoduleTypes, Module } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useI18n } from 'vue-i18n';

const moduleStore = useModuleStore();
const { t: $t } = useI18n();

const props = defineProps<{
  modelValue: string | null;
  moduleType: Module | string;
  submoduleType: AllSubmoduleTypes;
  field: ModuleField;
  entry: Record<string, unknown>;
  loading?: boolean;
  errors?: string | null | undefined;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void;
}>();

const formModel = computed({
  get() {
    return props.modelValue;
  },
  set(value: string | null) {
    emit('update:modelValue', value);
  },
});

const label = computed(() =>
  $t(`${props.field.labelKey || props.field.label}`, {
    submoduleTitle: $t(`${props.moduleType}-${props.submoduleType}`),
  }),
);

const isFieldReadOnly = computed(() => {
  if (props.field.disable || props.field.readOnly) return true;
  if (!props.field.readOnlyWhenFilled) return false;
  return false;
});

const fieldOptions = ref<Array<{ value: string; label: string }>>([]);

const fieldDisabled = ref<boolean>(false);

watchEffect(async () => {
  if (props.field.options) {
    fieldOptions.value = props.field.options;
    await setDefaultValue();
    return;
  }

  if (props.field.optionsFunction) {
    fieldOptions.value = await props.field.optionsFunction(
      props.submoduleType,
      props.entry,
    );
    await setDefaultValue();
    return;
  }

  const taxoNode = moduleStore.state.taxonomySubmodule[props.submoduleType];
  fieldOptions.value = taxoNode
    ? taxoNode.children.map((node) => ({
        label: node.label,
        value: node.name,
      }))
    : [];
  await setDefaultValue();
});

watchEffect(() => {
  if (typeof props.field.disable === 'function') {
    fieldDisabled.value = props.field.disable(props.submoduleType, props.entry);
  } else {
    fieldDisabled.value = !!props.field.disable;
  }
});

async function setDefaultValue() {
  if (props.field.default === undefined) {
    formModel.value = null;
  } else if (typeof props.field.default === 'function') {
    formModel.value = (await props.field.default(
      props.submoduleType,
      props.entry,
    )) as string | null;
  } else {
    formModel.value = props.field.default as string | null;
  }
}

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
</script>
