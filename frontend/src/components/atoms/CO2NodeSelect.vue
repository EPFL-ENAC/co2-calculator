<template>
  <q-select
    v-model="formModel"
    :options="options"
    emit-value
    map-options
    dense
    outlined
    class="co2-node-select"
    :loading="loading"
    :disable="props.field.disable || options.length === 0"
    :label="label"
    :hint="props.field.hint ? $t(props.field.hint) : undefined"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ModuleField } from 'src/constant/moduleConfig';
import type { AllSubmoduleTypes } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useI18n } from 'vue-i18n';

const moduleStore = useModuleStore();
const { t: $t } = useI18n();

const props = defineProps<{
  modelValue: string | null;
  submoduleType: AllSubmoduleTypes;
  path?: string[] | undefined;
  field: ModuleField;
  loading?: boolean;
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

const label = computed(() => {
  if (props.field.labelKey && typeof props.field.labelKey === 'string') {
    return $t(props.field.labelKey);
  }
  return props.field.label ? $t(props.field.label) : undefined;
});

const options = computed(() => {
  let taxoNode = moduleStore.state.taxonomySubmodule[props.submoduleType];
  if (props.path && taxoNode) {
    for (const nodeName of props.path) {
      const nextNode = taxoNode.children.find(
        (child) => child.name === nodeName,
      );
      if (!nextNode) {
        return [];
      }
      taxoNode = nextNode;
    }
  }
  return taxoNode
    ? taxoNode.children.map((node) => ({
        label: node.label,
        value: node.name,
      }))
    : [];
});
</script>
