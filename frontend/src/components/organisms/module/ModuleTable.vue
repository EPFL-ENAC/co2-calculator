<template>
  <div class="q-mb-sm flex justify-between items-center">
    <div class="text-body2 text-weight-medium">Table title (0)</div>
    <div>
      <q-btn
        outline
        icon="o_view_list"
        color="primary"
        :label="$t('common_upload_csv')"
        unelevated
        no-caps
        size="sm"
        class="text-weight-medium q-mr-sm"
      />
      <q-btn
        icon="download"
        color="accent"
        :label="$t('common_download_csv_template')"
        unelevated
        no-caps
        size="sm"
        class="text-weight-medium"
      />
    </div>
  </div>
  <q-table
    class="co2-table border"
    :columns="qCols"
    :rows="rows"
    row-key="id"
    :loading="loading"
    :error="error"
    flat
    no-data-label="No items"
  >
    <template #body="props">
      <q-tr :props="props" class="q-tr--no-hover">
        <q-td v-for="col in qCols" :key="col.name" :props="props">
          {{ renderCell(props.row, col) }}
        </q-td>
      </q-tr>
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
