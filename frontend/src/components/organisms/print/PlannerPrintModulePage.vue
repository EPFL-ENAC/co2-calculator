<script setup lang="ts">
import { computed } from 'vue';
import ReportPage from 'src/components/organisms/ReportPage.vue';
import PrintModuleTable from 'src/components/organisms/print/PrintModuleTable.vue';
import type { PlannerPrintTable } from 'src/composables/print/useProjectPlannerPrintData';
import type { PlannerPrintModule } from 'src/utils/plannerPrintModules';

interface Props {
  module: PlannerPrintModule;
  year: number;
  pageNumber: number;
  scope: string;
  tables: PlannerPrintTable[];
}

const props = defineProps<Props>();

const isPrefilled = computed(() => props.module.behavior === 'prefilled');
</script>

<template>
  <ReportPage
    :title="$t(module.type)"
    :scope="scope"
    :page-number="pageNumber"
    flow
  >
    <div class="module-header">
      <h2 class="text-h5 q-mt-none q-mb-none">{{ $t(module.type) }}</h2>
      <span v-if="isPrefilled" class="module-badge">
        {{ $t('planner_module_prefilled_badge') }}
      </span>
    </div>
    <div class="text-body2 text-secondary q-mb-lg">
      {{ $t('planner_print_module_subtitle', { year }) }}
    </div>

    <section
      v-for="table in tables"
      :key="table.sub.id"
      class="submodule-section"
    >
      <h3 v-if="table.sub.tableNameKey" class="text-body1 submodule-title">
        {{ $t(table.sub.tableNameKey, { count: table.rows.length }) }}
      </h3>
      <PrintModuleTable
        :submodule="table.sub"
        :module-config="module.config"
        :rows="table.rows"
        :show-reference-columns="isPrefilled"
      />
    </section>
  </ReportPage>
</template>

<style scoped lang="scss">
.module-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.module-badge {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 2px 6px;
  border: 1px solid var(--half-muted-color);
  border-radius: 999px;
  opacity: 0.75;
}

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
