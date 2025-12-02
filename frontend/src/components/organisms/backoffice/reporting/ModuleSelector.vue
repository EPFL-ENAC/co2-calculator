<script setup lang="ts">
import type { ModuleCard } from 'src/constant/moduleCards';
import { MODULE_STATES, type ModuleState } from 'src/constant/moduleStates';
import { computed } from 'vue';
import type { Module } from 'src/constant/modules';

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
</script>

<template>
  <div class="container container--pa-sm full-width">
    <div class="flex justify-between">
      <div class="q-gutter-sm row items-center">
        <q-icon :name="moduleCard.icon" color="accent" size="xs" />
        <h3 class="text-h6 text-weight-medium">
          {{ $t(moduleCard.module) }}
        </h3>
      </div>
    </div>
    <div class="q-mt-sm">
      <q-checkbox
        v-for="state in Object.values(MODULE_STATES)"
        :key="state"
        :model-value="selectedStates.includes(state)"
        size="sm"
        color="accent"
        :label="$t(state)"
        class="q-mr-md"
        @update:model-value="(checked) => toggleState(state, checked)"
      />
    </div>
  </div>
</template>
