<template>
  <q-page class="module-page">
    <module-title
      :type="currentModuleType"
      :has-description="currentModuleConfig.hasDescription"
      :has-description-subtext="currentModuleConfig.hasDescriptionSubtext"
      :has-tooltip="currentModuleConfig.hasTooltip"
    />
    <module-charts :type="currentModuleType" />
    <!-- module tables iteration -->
    <module-table-section
      v-if="currentModuleType === MODULES.EquipmentElectricConsumption"
      :type="currentModuleType"
      :data="data"
      :loading="loading"
      :error="error"
      :unit-id="unit"
      :year="year"
    />
    <!-- module summary -->
    <module-total-result
      v-if="
        (
          [MODULES.EquipmentElectricConsumption, MODULES.MyLab] as Module[]
        ).includes(currentModuleType)
      "
      :data="data?.totals?.total_kg_co2eq"
      :type="currentModuleType"
    />
  </q-page>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';
import { computed, onMounted, watch, Ref } from 'vue';

import ModuleTitle from 'src/components/organisms/module/ModuleTitle.vue';
import ModuleCharts from 'src/components/organisms/module/ModuleCharts.vue';
import ModuleTableSection from 'src/components/organisms/module/ModuleTableSection.vue';
import ModuleTotalResult from 'src/components/organisms/module/ModuleTotalResult.vue';
import { Module, MODULES } from 'src/constant/modules';
import { useModuleStore } from 'src/stores/modules';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULES_CONFIG } from 'src/constant/module-config';

const $route = useRoute();
const currentModuleType = computed(() => $route.params.module as Module);

const currentModuleConfig: Ref<ModuleConfig> = computed(
  () => MODULES_CONFIG[currentModuleType.value] as ModuleConfig,
);

// compute unit and year from route params
const unit = computed(() => String($route.params.unit ?? 'default'));
const year = computed(() =>
  String($route.params.year ?? new Date().getFullYear()),
);

const moduleStore = useModuleStore();

const data = computed(() => moduleStore.state.data);
const loading = computed(() => moduleStore.state.loading);
const error = computed(() => moduleStore.state.error);

// get data on mount and when route params change
const getData = () => {
  if (!currentModuleType.value) return;
  if (currentModuleType.value != MODULES.EquipmentElectricConsumption) {
    console.warn(
      `ModulePage: No data fetching implemented for module type ${currentModuleType.value}`,
    );
    moduleStore.state.data = null;
    moduleStore.state.loading = false;
    moduleStore.state.error = null;
    return;
  }
  moduleStore.getModuleData(currentModuleType.value, unit.value, year.value);
};

onMounted(getData);
watch(
  [() => currentModuleType.value, () => unit.value, () => year.value],
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
  max-width: tokens.$layout-page-width;
  // center the page
  justify-self: center; // center within the parent grid cell
}
</style>
