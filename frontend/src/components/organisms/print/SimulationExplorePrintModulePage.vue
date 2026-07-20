<script setup lang="ts">
import ReportPage from 'src/components/organisms/ReportPage.vue';
import PrintModuleTable from 'src/components/organisms/print/PrintModuleTable.vue';
import type { ExploreModule } from 'src/utils/exploreModules';
import type { PrintRow } from 'src/utils/printTable';

interface Props {
  module: ExploreModule;
  pageNumber: number;
  currentYear: number;
  submoduleRows: Record<string, PrintRow[]>;
  headcountMembers: Map<string, string>;
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
