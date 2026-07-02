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
    :no-data-label="$t('common_no_items')"
    :rows-per-page-label="$t('rows_per_page')"
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

        <!-- tCO₂-eq -->
        <q-td key="tco2eq" :props="props" class="text-center">
          <span class="text-weight-bold">{{ nOrDash(props.row.tco2eq) }}</span>
        </q-td>
      </q-tr>
    </template>
  </q-table>
</template>

<!-- Not scoped: .co2-table's rules reach into Quasar's rendered table internals
     (thead/tbody/td/tr), which do not receive scoped style attributes. -->
<style lang="scss">
@use 'src/css/02-tokens' as tokens;

.co2-table {
  border: 1px solid tokens.$container-default-border;
  border-radius: tokens.$table-border-radius;
  font-size: tokens.$text-size-sm;

  /* height or max-height is important for sticky header */
  max-height: tokens.$table-max-height;
  overflow-y: auto;

  th {
    font-size: tokens.$text-size-sm;
  }

  thead tr th {
    position: sticky;
    z-index: tokens.$table-header-z-index;
    background-color: tokens.$table-bg-odd;
  }

  thead tr:first-child th {
    top: 0;
  }

  .q-table td {
    border: none;
  }

  tbody .q-tr:nth-child(even) {
    background-color: tokens.$table-bg-even;
  }

  tr {
    &::before {
      display: none !important;
    }
  }

  &--selectable {
    tbody tr {
      cursor: pointer;

      &.selected > td {
        border-top: 1px solid tokens.$container-selected-hover-border !important;
        border-bottom: 1px solid tokens.$container-selected-hover-border !important;
      }

      &.selected:first-child > td {
        border-top: none !important;
        border-bottom: 1px solid tokens.$container-selected-hover-border !important;
      }

      &.selected:last-child > td {
        border-top: 1px solid tokens.$container-selected-hover-border !important;
        border-bottom: none !important;
      }
    }
  }

  .square-button {
    padding: tokens.$spacing-sm tokens.$spacing-sm;
  }
}
</style>
