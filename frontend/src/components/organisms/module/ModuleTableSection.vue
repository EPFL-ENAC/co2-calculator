<template>
  <div>
    <div class="module-table-section__submodules">
      <template v-for="sub in visibleSubmodules" :key="sub.id">
        <sub-module-section
          :submodule="sub"
          :module-config="currentModuleConfig"
          :module-type="type"
          :disable="disable"
          :submodule-type="sub.type"
          :data="data"
          :loading="loading"
          :error="error"
          :unit-id="unitId"
          :year="year"
          :factor-year="factorYear"
          :carbon-report-id="carbonReportId"
          :show-reference-columns="showReferenceColumns"
          :project-years-count="projectYearsCount"
          :percentage-locked="percentageLocked"
          :exclude-snapshots="excludeSnapshots"
          :show-grant-budget="showGrantBudgets"
          :grant-budget="grantBudgets?.[sub.id] ?? null"
          :grant-budget-currency="grantBudgetCurrency"
          :threshold="currentModuleConfig.threshold || defaultThreshold"
          :tooltip-scope="tooltipScope"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, Ref } from 'vue';
import { ModuleConfig } from 'src/constant/moduleConfig';
import { MODULES_CONFIG } from 'src/constant/module-config';
import SubModuleSection from 'src/components/organisms/module/SubModuleSection.vue';

import type { ModuleResponse } from 'src/constant/modules';
import { MODULES_THRESHOLD_TYPES, type Threshold } from 'src/constant/modules';

import { Module } from 'src/constant/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import type { TooltipScope } from 'src/utils/tooltipScope';

const props = defineProps<{
  type: Module;
  data: ModuleResponse | null;
  loading: boolean;
  error: string | null;
  unitId: number;
  year: string | number;
  /** Year whose factors the class/subclass options resolve against — see ModuleForm. */
  factorYear?: number | null;
  disable: boolean;
  /**
   * Plan-year report id. When set (Simulator Plan), module calls address this
   * report directly instead of resolving unit/year — a unit can hold several
   * plans with overlapping years, so unit/year cannot identify the report.
   */
  carbonReportId?: number;
  /** Planner prefilled: show the reference-kg column + % slider. */
  showReferenceColumns?: boolean;
  /** Planner Project Grant: plan year count for the "× project years" column. */
  projectYearsCount?: number | null;
  /** Grant equipment global mode: per-row % controls read-only (#1981). */
  percentageLocked?: boolean;
  /** Grant equipment global mode: list only manually added entries (#1981). */
  excludeSnapshots?: boolean;
  /** Planner Project Grant: show a budget field above each submodule table. */
  showGrantBudgets?: boolean;
  /** Grant submodule budgets of this module, keyed by submodule id (#1978). */
  grantBudgets?: Record<string, number> | null;
  /** Which space these tables render in; selects the tooltip text set. */
  tooltipScope?: TooltipScope;
  /** Currency code of the grant budget, shown on the budget fields. */
  grantBudgetCurrency?: string | null;
  /**
   * Replaces the Calculator MODULES_CONFIG entry — the Simulator Plan
   * renders planner-specific submodules (see constant/planner-module-config).
   * When set, the year-configuration submodule filter is skipped: planner
   * modules are toggled by the plan's own Active checkbox instead.
   */
  configOverride?: ModuleConfig;
}>();

const yearConfigStore = useYearConfigStore();

const currentModuleConfig: Ref<ModuleConfig> = computed(
  () => props.configOverride ?? (MODULES_CONFIG[props.type] as ModuleConfig),
);

const visibleSubmodules = computed(() => {
  if (props.configOverride) return currentModuleConfig.value.submodules;
  const unifiedConfig = yearConfigStore.getModule(props.type);
  if (!unifiedConfig) return currentModuleConfig.value.submodules;

  return currentModuleConfig.value.submodules.filter((sub) => {
    const subConfig = unifiedConfig.submodules[sub.id];
    return subConfig?.enabled ?? true;
  });
});

const defaultThreshold: Threshold = {
  type: MODULES_THRESHOLD_TYPES[0],
  value: 0,
};
</script>

<style scoped lang="scss">
.module-table-section__submodules {
  display: grid;
  grid-gap: 1rem;
}
</style>
