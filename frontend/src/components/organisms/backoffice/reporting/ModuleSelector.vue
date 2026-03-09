<script setup lang="ts">
import type { ModuleCard } from 'src/constant/moduleCards';
import { MODULE_STATES, type ModuleState } from 'src/constant/moduleStates';
import { computed } from 'vue';
import type { Module } from 'src/constant/modules';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

export interface ModuleStateData {
  module: Module;
  states: ModuleState[];
}

const props = defineProps<{
  moduleCard: ModuleCard;
  modelValue: ModuleState[];
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', states: ModuleState[]): void;
  (e: 'update', data: ModuleStateData): void;
}>();

const selectedStates = computed({
  get: () => props.modelValue,
  set: (value) => {
    emit('update:modelValue', value);
    emit('update', {
      module: props.moduleCard.module,
      states: [...value],
    });
  },
});

function toggleState(state: ModuleState, checked: boolean) {
  if (checked) {
    if (!selectedStates.value.includes(state)) {
      selectedStates.value = [...selectedStates.value, state];
    }
  } else {
    selectedStates.value = selectedStates.value.filter((s) => s !== state);
  }
}

const MODULE_STATE_LABELS: Record<keyof typeof MODULE_STATES, string> = {
  Default: 'backoffice_reporting_csv_default',
  InProgress: 'backoffice_reporting_csv_in_progress',
  Validated: 'backoffice_reporting_csv_validated',
};
const moduleStateKeys = Object.keys(
  MODULE_STATES,
) as (keyof typeof MODULE_STATES)[];
</script>

<template>
  <div class="container container--pa-sm full-width">
    <div class="flex justify-between">
      <div class="q-gutter-sm row items-center">
        <module-icon :name="moduleCard.module" size="md" color="accent" />
        <h3 class="text-h6 text-weight-medium">
          {{ $t(moduleCard.module) }}
        </h3>
      </div>
    </div>
    <div class="q-mt-sm">
      <q-checkbox
        v-for="state in moduleStateKeys"
        :key="state"
        :model-value="
          selectedStates.includes(
            MODULE_STATES[state as keyof typeof MODULE_STATES],
          )
        "
        size="sm"
        color="accent"
        :label="$t(MODULE_STATE_LABELS[state as keyof typeof MODULE_STATES])"
        class="q-mr-md"
        @update:model-value="
          (checked) =>
            toggleState(
              MODULE_STATES[state as keyof typeof MODULE_STATES],
              checked,
            )
        "
      />
    </div>
  </div>
</template>
