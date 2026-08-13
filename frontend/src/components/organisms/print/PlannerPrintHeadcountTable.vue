<script setup lang="ts">
import { computed } from 'vue';
import type { PlannerHeadcountRow } from 'src/utils/plannerHeadcountRows';
import { plannerHeadcountLabelKey } from 'src/constant/planner-headcount';

const props = defineProps<{ rows: PlannerHeadcountRow[] }>();

const totalFte = computed(() =>
  props.rows.reduce((sum, row) => sum + row.fte, 0),
);
</script>

<template>
  <h3 class="text-body1 table-title">
    {{ $t('planner_headcount_table_title') }}
  </h3>
  <table class="print-table">
    <thead>
      <tr>
        <th>{{ $t('planner_headcount_category_col') }}</th>
        <th class="align-right">{{ $t('planner_headcount_fte_col') }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="row in rows" :key="row.sius_code">
        <td>{{ $t(plannerHeadcountLabelKey(row.sius_code)) }}</td>
        <td class="align-right">
          {{ $nOrDash(row.fte, { options: { maximumFractionDigits: 1 } }) }}
        </td>
      </tr>
    </tbody>
    <tfoot>
      <tr>
        <td class="text-weight-medium">
          {{ $t('planner_headcount_total_fte') }}
        </td>
        <td class="align-right text-weight-medium">
          {{ $nOrDash(totalFte, { options: { maximumFractionDigits: 1 } }) }}
        </td>
      </tr>
    </tfoot>
  </table>
</template>

<style scoped lang="scss">
.table-title {
  font-weight: 500;
  margin: 0 0 6px;
  break-after: avoid;
  page-break-after: avoid;
}

.print-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 9px;

  th,
  td {
    border: 1px solid var(--half-muted-color);
    padding: 2px 4px;
    word-break: break-word;
    vertical-align: top;
  }

  th {
    font-weight: 600;
  }

  thead {
    display: table-header-group;
  }

  tr {
    break-inside: avoid;
    page-break-inside: avoid;
  }
}

.align-right {
  text-align: right;
}
</style>
