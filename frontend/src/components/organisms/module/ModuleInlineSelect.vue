<template>
  <div class="inline-select-wrapper">
    <div
      v-if="
        isSubClass &&
        !loadingSubclasses &&
        (!subClassOptions || subClassOptions.length === 0) &&
        !model
      "
      class="inline-subclass-placeholder"
    ></div>
    <q-select
      v-else
      v-model="model"
      :options="options"
      emit-value
      map-options
      dense
      outlined
      hide-bottom-space
      class="inline-input"
      :loading="isClass ? loadingClasses : loadingSubclasses"
      @update:model-value="onChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue';
import { QSelect } from 'quasar';
import { useModulePowerFactors } from 'src/composables/useModulePowerFactors';
import type { Module } from 'src/constant/modules';

type ModuleSubType = 'scientific' | 'it' | 'other';

interface ModuleRow {
  id: string | number;
  // allow arbitrary additional fields
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  [key: string]: any;
}

const props = defineProps<{
  row: ModuleRow;
  fieldId: string;
  moduleType: Module | string;
  submoduleType?: ModuleSubType;
  unitId: string;
  year: string | number;
}>();

const isClass = computed(() => props.fieldId === 'class');
const isSubClass = computed(() => props.fieldId === 'sub_class');

const { dynamicOptions, loadingClasses, loadingSubclasses } =
  useModulePowerFactors(props.row, toRef(props, 'submoduleType'));

const classOptions = computed(() => dynamicOptions['class'] ?? []);
const subClassOptions = computed(() => dynamicOptions['sub_class'] ?? []);

const options = computed(() =>
  isClass.value ? classOptions.value : subClassOptions.value,
);

const model = computed({
  get() {
    return props.row[props.fieldId] ?? '';
  },
  set(val: unknown) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (props.row as any)[props.fieldId] = val;
  },
});

async function onChange() {
  // Persist the changed field to the backend along with any
  // power-factor-derived fields updated by the composable.
  const { useModuleStore } = await import('src/stores/modules');
  const store = useModuleStore();
  const idNum = Number(props.row.id);
  if (!Number.isFinite(idNum)) return;

  const payload: Record<string, string | number | boolean | null> = {
    [props.fieldId]: model.value as string | number | boolean | null,
  };

  // If act_power / pas_power are present on the row (and likely
  // have been refreshed by useModulePowerFactors), include them so
  // backend stays in sync with derived values.
  if ('act_power' in props.row) {
    payload.act_power = props.row.act_power as string | number | boolean | null;
  }
  if ('pas_power' in props.row) {
    payload.pas_power = props.row.pas_power as string | number | boolean | null;
  }

  await store.patchItem(
    props.moduleType as Module,
    props.unitId,
    String(props.year),
    idNum,
    payload,
  );
}
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.inline-select-wrapper {
  width: 100%;
}

.inline-subclass-placeholder {
  width: 100%;
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

.inline-input {
  width: 140px;
}
</style>
