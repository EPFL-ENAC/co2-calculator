<template>
  <q-page>
    <Co2Timeline />
    <q-separator />
    <div class="module-page">
      <module-title
        :type="currentModuleType"
        :has-description="currentModuleConfig.hasDescription"
        :has-description-subtext="currentModuleConfig.hasDescriptionSubtext"
        :has-tooltip="currentModuleConfig.hasTooltip"
      />
      <!-- module summary -->
      <module-total-result
        v-if="
          (
            [MODULES.EquipmentElectricConsumption, MODULES.MyLab] as Module[]
          ).includes(currentModuleType)
        "
        :data="totalResult"
        :type="currentModuleType"
        :module-config="currentModuleConfig"
      />
      <module-charts :type="currentModuleType" />
      <!-- module tables iteration -->
      <module-table-section
        v-if="
          (
            [MODULES.EquipmentElectricConsumption, MODULES.MyLab] as Module[]
          ).includes(currentModuleType)
        "
        :type="currentModuleType"
        :data="data"
        :loading="loading"
        :error="error"
        :unit-id="workspaceStore.selectedUnit?.id"
        :year="workspaceStore.selectedYear"
        :disable="timelineStore.canEdit === false"
      />
      <module-navigation :current-module="currentModuleType" />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { computed, onMounted, watch, Ref } from 'vue';

import ModuleTitle from 'src/components/organisms/module/ModuleTitle.vue';
import ModuleCharts from 'src/components/organisms/module/ModuleCharts.vue';
import ModuleTableSection from 'src/components/organisms/module/ModuleTableSection.vue';
import ModuleTotalResult from 'src/components/organisms/module/ModuleTotalResult.vue';
import ModuleNavigation from 'src/components/organisms/module/ModuleNavigation.vue';
import { Module, MODULES } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULES_CONFIG } from 'src/constant/module-config';
import Co2Timeline from 'src/components/organisms/layout/Co2Timeline.vue';

const $route = useRoute();
const currentModuleType = computed(() => $route.params.module as Module);
import { useTimelineStore } from 'src/stores/modules';
const timelineStore = useTimelineStore();

const currentModuleConfig: Ref<ModuleConfig> = computed(
  () => MODULES_CONFIG[currentModuleType.value] as ModuleConfig,
);

const workspaceStore = useWorkspaceStore();

const moduleStore = useModuleStore();

// COMPUTED
const data = computed(() => moduleStore.state.data);
const loading = computed(() => moduleStore.state.loading);
const error = computed(() => moduleStore.state.error);
const totalResult = computed(() => {
  if (currentModuleType.value === MODULES.MyLab) {
    return moduleStore.state.data?.totals?.total_annual_fte;
  }
  return moduleStore.state.data?.totals?.total_tonnes_co2eq;
});

const AuthorizedModules: Module[] = [
  MODULES.EquipmentElectricConsumption,
  MODULES.MyLab,
];

// ACTIONS
// get data on mount and when route params change
const getData = () => {
  if (!currentModuleType.value) return;
  if (
    currentModuleType.value &&
    !AuthorizedModules.includes(currentModuleType.value)
  ) {
    console.warn(
      `ModulePage: No data fetching implemented for module type ${currentModuleType.value}`,
    );
    moduleStore.state.data = null;
    moduleStore.state.loading = false;
    moduleStore.state.error = null;
    return;
  }
  moduleStore.getModuleTotals(
    currentModuleType.value,
    String(workspaceStore.selectedUnit?.id),
    String(workspaceStore.selectedYear),
  );
};

onMounted(getData);
watch(
  [
    () => currentModuleType.value,
    () => workspaceStore.selectedUnit,
    () => workspaceStore.selectedYear,
  ],
  getData,
);
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;
.module-page {
  padding-top: tokens.$template-padding-y;
  padding-bottom: tokens.$template-padding-y;
  display: grid;
  grid-auto-flow: row;
  row-gap: tokens.$template-gap;
  align-items: start;
  grid-auto-rows: max-content;
  width: 100%;

  // center the page
  justify-self: center; // center within the parent grid cell
}
</style>
