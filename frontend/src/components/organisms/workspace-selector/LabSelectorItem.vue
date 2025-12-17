<script setup lang="ts">
import { computed } from 'vue';
import { MODULES_LIST } from 'src/constant/modules';
import { ROLES } from 'src/constant/roles';
import { useWorkspaceStore } from 'src/stores/workspace';

const props = defineProps<{
  selected?: boolean;
  unit: {
    id: string;
    name: string;
    principal_user_id: string;
    principal_user_function: string;
    principal_user_name: string;
    current_user_role: string;
    affiliations: string[];
  };
}>();

const workspaceStore = useWorkspaceStore();

const latestYear = computed(() => workspaceStore.getLatestYear(props.unit.id));

const completedModules = 0;
</script>

<template>
  <q-card
    flat
    outlined
    class="container lab-selector-item"
    :class="{ 'lab-selector-item--selected': selected }"
  >
    <div class="row items-center justify-between">
      <h3 class="text-h4 text-weight-bold">{{ unit.name }}</h3>
      <q-badge
        v-if="unit.current_user_role"
        rounded
        :outline="unit.current_user_role !== ROLES.PrincipalUser"
        :color="
          unit.current_user_role === ROLES.PrincipalUser ? 'accent' : 'primary'
        "
        :label="$t(unit.current_user_role)"
        class="q-pa-sm"
      />
    </div>
    <div class="row items-center justify-between q-mt-xl">
      <span class="text-body2 text-weight-medium">{{
        $t('workspace_setup_unit_manager')
      }}</span>
      <span class="text-body2 text-weight-bold">{{
        unit.principal_user_name
      }}</span>
    </div>
    <q-separator class="q-my-sm" :color="selected ? 'accent' : 'grey-4'" />
    <div class="row items-center justify-between">
      <span class="text-body2 text-weight-medium">{{
        $t('workspace_setup_unit_affiliation')
      }}</span>
      <span class="text-body2 text-weight-bold">{{
        unit.affiliations.join(' / ')
      }}</span>
    </div>
    <div class="q-mt-xl">
      <div class="row items-center justify-between q-mb-xs">
        <span class="text-body2 text-weight-medium">{{
          $t('workspace_setup_unit_progress', {
            year: latestYear || new Date().getFullYear(),
          })
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
          :class="{ filled: i <= completedModules, selected: selected }"
        ></div>
      </div>
    </div>
  </q-card>
</template>
