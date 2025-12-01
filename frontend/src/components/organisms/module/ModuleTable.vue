<template>
  <q-table
    :columns="qCols"
    :rows="rows"
    row-key="id"
    :loading="loading"
    :error="error"
    flat
    bordered
    dense
    no-data-label="No items"
  >
    <template #body-cell="slotProps">
      <q-td :props="slotProps">
        {{ renderCell(slotProps.row, slotProps.col) }}
      </q-td>
    </template>

    <template #no-data>
      <div class="text-center q-pa-md">No data available</div>
    </template>
  </q-table>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { TableColumn } from 'src/constant/moduleConfig';

type RowValue = string | number | boolean | null | undefined;
type ModuleRow = Record<string, RowValue> & { id: string | number };

const props = defineProps<{
  columns?: TableColumn[] | null;
  rows?: ModuleRow[];
  loading?: boolean;
  error?: string | null;
}>();

// simple local rows by default (can be passed via prop)
// const rows = ref(props.rows ?? []);

const qCols = computed(() => {
  return (props.columns ?? []).map((c) => ({
    name: c.key,
    label: c.unit ? `${c.label} (${c.unit})` : c.label,
    field: c.key,
    sortable: !!c.sortable,
  }));
});

function renderCell(row: ModuleRow, col: { field: string }) {
  const val = row[col.field];
  if (val === undefined || val === null) return '-';
  return String(val);
}
</script>
<style scoped></style>
