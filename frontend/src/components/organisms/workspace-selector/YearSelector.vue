<script setup lang="ts">
import { computed } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';

const ROWS_PER_PAGE = 20;

interface YearData {
  year: number;
  progress: number;
  completed_modules: number;
  comparison: number | null;
  kgco2: number;
  status: 'future' | 'current' | 'complete';
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
    name: 'kgco2',
    label: t('workspace_setup_year_table_header_kgco2'),
    field: 'kgco2',
    align: 'right',
    sortable: true,
  },
]);
</script>

<template>
  <q-table
    class="co2-table"
    table-class=" co2-table--selectable"
    header-class="text-weight-bold"
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

        <!-- kg CO2 -->
        <q-td key="kgco2" :props="props" class="text-center">
          <span class="text-weight-medium"
            >{{ props.row.kgco2.toLocaleString() }}kg</span
          >
        </q-td>
      </q-tr>
    </template>
  </q-table>
</template>
