<script setup lang="ts">
import ReportPage from '@/components/organisms/ReportPage.vue';
import PlannerPrintHeadcountTable from '@/components/organisms/print/PlannerPrintHeadcountTable.vue';
import PrintModuleTable from '@/components/organisms/print/PrintModuleTable.vue';
import { MODULES } from '@/constant/modules';
import type { ExploreModule } from '@/utils/exploreModules';
import type { PlannerHeadcountRow } from '@/utils/plannerHeadcountRows';
import type { PrintRow } from '@/utils/printTable';

interface Props {
  module: ExploreModule;
  pageNumber: number;
  currentYear: number;
  submoduleRows: Record<string, PrintRow[]>;
  headcountMembers: Map<string, string>;
  plannerHeadcountRows: PlannerHeadcountRow[];
}

defineProps<Props>();
</script>

<template>
  <ReportPage :title="$t(module.type)" :page-number="pageNumber" flow>
    <h2 class="text-h5 q-mt-none">
      {{ $t(module.type) }}
    </h2>
    <div class="text-body2 text-secondary q-mb-lg">
      {{ $t('simulation_explore_print_subtitle', { year: currentYear }) }}
    </div>

    <!-- Headcount is the Planner's fixed SIUS-category grid (#2070), not
         the Calculator submodule tables. -->
    <section v-if="module.type === MODULES.Headcount" class="submodule-section">
      <PlannerPrintHeadcountTable
        v-if="plannerHeadcountRows.length"
        :rows="plannerHeadcountRows"
      />
      <div v-else class="text-body2 text-secondary">
        {{ $t('common_no_data_available') }}
      </div>
    </section>
    <template v-else>
      <section
        v-for="sub in module.submodules"
        :key="sub.id"
        class="submodule-section"
      >
        <h3 v-if="sub.tableNameKey" class="text-body1 submodule-title">
          {{
            $t(sub.tableNameKey, {
              count: (submoduleRows[sub.id] ?? []).length,
            })
          }}
        </h3>
        <PrintModuleTable
          v-if="(submoduleRows[sub.id] ?? []).length"
          :submodule="sub"
          :module-config="module.config"
          :rows="submoduleRows[sub.id] ?? []"
          :headcount-members="headcountMembers"
        />
        <div v-else class="text-body2 text-secondary">
          {{ $t('common_no_data_available') }}
        </div>
      </section>
    </template>
  </ReportPage>
</template>

<style scoped lang="scss">
.submodule-section {
  margin-bottom: 16px;
}

.submodule-title {
  font-weight: 500;
  margin: 0 0 6px;
  break-after: avoid;
  page-break-after: avoid;
}
</style>
