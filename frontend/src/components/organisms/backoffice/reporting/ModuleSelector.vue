<script setup lang="ts">
import type { ModuleCard } from 'src/constant/moduleCards';
import { MODULE_STATES, type ModuleState } from 'src/constant/moduleStates';
import { computed, ref, watch } from 'vue';
import type { Module } from 'src/constant/modules';

export interface ModuleStateData {
  module: Module;
  states: ModuleState[];
}

const props = defineProps<{
  moduleCard: ModuleCard;
}>();

const emit = defineEmits<{
  (e: 'update', data: ModuleStateData): void;
  (e: 'enabled-change', module: Module, enabled: boolean): void;
}>();

const selectedStates = ref<ModuleState[]>([]);
const enabled = ref<boolean>(false);

const isDisabled = computed(() => !enabled.value);

function toggleState(state: ModuleState) {
  const index = selectedStates.value.indexOf(state);
  if (index > -1) {
    selectedStates.value.splice(index, 1);
  } else {
    selectedStates.value.push(state);
  }
  emitUpdate();
}

function emitUpdate() {
  emit('update', {
    module: props.moduleCard.module,
    states: [...selectedStates.value],
  });
  emit('enabled-change', props.moduleCard.module, enabled.value);
}

watch(enabled, () => {
  emitUpdate();
});
</script>

<template>
  <div
    class="container container--pa-sm full-width"
    :class="{ 'container--selected': enabled }"
  >
    <div class="flex justify-between">
      <div class="q-gutter-sm row items-center">
        <q-icon
          :name="moduleCard.icon"
          :color="isDisabled ? 'grey-5' : 'accent'"
          size="xs"
        />
        <h3
          class="text-h6 text-weight-medium"
          :class="{ 'text-grey-5': isDisabled }"
        >
          {{ $t(moduleCard.module) }}
        </h3>
      </div>
      <q-checkbox
        v-model="enabled"
        color="accent"
        size="xs"
        class="text-weight-medium"
      />
    </div>
    <div>
      <q-checkbox
        v-for="state in Object.values(MODULE_STATES)"
        :key="state"
        :model-value="selectedStates.includes(state)"
        size="sm"
        :color="isDisabled ? 'grey-5' : 'accent'"
        :label="$t(state)"
        :disable="isDisabled"
        class="q-mr-md"
        @update:model-value="toggleState(state)"
      />
    </div>
  </div>
</template>
