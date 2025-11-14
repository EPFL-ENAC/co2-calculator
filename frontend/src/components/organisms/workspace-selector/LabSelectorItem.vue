<script setup lang="ts">
import { MODULES_LIST } from 'src/constant/modules';

const props = defineProps<{
  selected?: boolean;
  data: {
    id: string;
    name: string;
    role: string;
    years?: Record<
      string,
      {
        completed_modules: number;
        kgco2: number;
        last_year_comparison?: number;
        report: string;
      }
    >;
  };
}>();

// Get the most recent year's completed modules
const completedModules =
  props.data.years?.[
    Math.max(...Object.keys(props.data.years || {}).map(Number))
  ]?.completed_modules || 0;
</script>

<template>
  <q-card
    flat
    outlined
    class="container lab-selector-item"
    :class="{ 'lab-selector-item--selected': selected }"
  >
    <div class="row items-center justify-between">
      <h3 class="text-h4 text-weight-bold">{{ data.name }}</h3>

      <div class="flex row q-gutter-sm items-center">
        <span class="text-body2 text-weight-bold">{{
          $t('workspace_setup_unit_role')
        }}</span>
        <q-badge
          rounded
          color="accent"
          :label="data.role"
          class="q-pa-sm rounded-borders"
        />
      </div>
    </div>
    <div class="row items-center justify-between q-mt-xl">
      <span class="text-body2 text-weight-medium">{{
        $t('workspace_setup_unit_manager')
      }}</span>
      <span class="text-body2 text-weight-bold">BLA</span>
    </div>
    <q-separator class="q-my-sm" />
    <div class="row items-center justify-between">
      <span class="text-body2 text-weight-medium">{{
        $t('workspace_setup_unit_affiliation')
      }}</span>
      <span class="text-body2 text-weight-medium">BLA</span>
    </div>
    <div class="q-mt-xl">
      <div class="row items-center justify-between q-mb-xs">
        <span class="text-body2 text-weight-medium">{{
          $t('workspace_setup_unit_progress')
        }}</span>
        <span class="text-body2 text-weight-medium"
          >{{ completedModules }}/{{ MODULES_LIST.length }}</span
        >
      </div>
      <div class="progress-segments q-my-sm">
        <div
          v-for="i in MODULES_LIST.length"
          :key="i"
          class="segment"
          :class="{ filled: i <= completedModules }"
        />
      </div>
    </div>
  </q-card>
</template>
