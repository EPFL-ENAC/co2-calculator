<script setup lang="ts">
import { computed } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';
import { nOrDash } from 'src/utils/number';

const ROWS_PER_PAGE = 20;

export interface YearData {
  year: number;
  tco2eq: number | null;
  status: string;
}

interface Props {
  years: YearData[];
  selectedYear?: number | null;
}

defineProps<Props>();

const emit = defineEmits<{
  (e: 'select', year: number): void;
}>();

function selectYear(year: number) {
  emit('select', year);
}

const { t } = useI18n();

const columns = computed<QTableColumn[]>(() => [
  {
    name: 'year',
    label: t('workspace_setup_year_table_header_year'),
    field: 'year',
    align: 'left',
    sortable: true,
  },
  {
    name: 'tco2eq',
    label: t('tco2eq'),
    field: 'tco2eq',
    align: 'right',
    sortable: true,
  },
]);
</script>

<template>
  <q-table
    class="co2-table border"
    table-class=" co2-table--selectable"
    :rows="years"
    :columns="columns"
    row-key="year"
    :rows-per-page-options="[ROWS_PER_PAGE]"
  >
    <template #body="props">
      <q-tr
        :props="props"
        class="q-tr--no-hover"
        :class="{
          selected: props.row.year === selectedYear,
          'bg-grey-1':
            props.row.year !== selectedYear && props.rowIndex % 2 === 1,
        }"
        @click="selectYear(props.row.year)"
      >
        <!-- Year -->
        <q-td key="year" :props="props">
          <span class="text-h6 text-weight-medium">{{ props.row.year }}</span>
        </q-td>

        <!-- tCO2-eq -->
        <q-td key="tco2eq" :props="props" class="text-center">
          <span class="text-weight-bold">{{ nOrDash(props.row.tco2eq) }}</span>
        </q-td>
      </q-tr>
    </template>
  </q-table>
</template>
