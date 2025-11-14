<script setup lang="ts">
import { ref } from 'vue';

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

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'select', year: number): void;
}>();
</script>

<template>
  <q-table
    class="co2-table"
    header-class="text-weight-bold"
    :rows="years"
    :columns="[
      {
        name: 'year',
        label: 'Year',
        field: 'year',
        align: 'left',
        sortable: true,
      },
      {
        name: 'progress',
        label: 'Progress',
        field: 'progress',
        align: 'right',
        sortable: true,
      },
      {
        name: 'comparison',
        label: 'Last Year Comparison',
        field: 'comparison',
        align: 'right',
        sortable: true,
      },
      {
        name: 'kgco2',
        label: 'kg CO2-eq',
        field: 'kgco2',
        align: 'right',
        sortable: true,
      },
    ]"
    row-key="year"
    :rows-per-page-options="[ROWS_PER_PAGE]"
  >
    <template #body="props">
      <q-tr :props="props" :class="{ 'bg-grey-1': props.rowIndex % 2 === 1 }">
        <!-- Year -->
        <q-td key="year" :props="props">
          <span class="text-h6 text-weight-medium">{{ props.row.year }}</span>
        </q-td>

        <!-- Progress -->
        <q-td key="progress" :props="props">
          <span
            :class="
              props.row.completed_modules === 7
                ? 'text-positive'
                : 'text-grey-7'
            "
            >{{ props.row.completed_modules }}/7</span
          >
        </q-td>

        <!-- Last Year Comparison -->
        <q-td key="comparison" :props="props" class="text-center">
          <span
            v-if="props.row.comparison !== null"
            :class="
              props.row.comparison > 0 ? 'text-negative' : 'text-positive'
            "
          >
            {{ props.row.comparison > 0 ? '+' : '' }}{{ props.row.comparison }}%
          </span>
          <span v-else class="text-grey-5">—</span>
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
