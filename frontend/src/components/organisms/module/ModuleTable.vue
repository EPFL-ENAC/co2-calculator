<template>
  <div class="q-mb-md flex justify-between items-center">
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
    <template #body="slotProps">
      <q-tr :props="{ props: slotProps }" class="q-tr--no-hover">
        <q-td
          v-for="col in qCols"
          :key="col.name"
          :props="slotProps"
          :align="col.align"
        >
          <template v-if="col.name === 'action'">
            <!-- Placeholder for action buttons, etc. -->
            <q-btn
              icon="o_edit"
              color="grey-4"
              text-color="primary"
              unelevated
              no-caps
              outline
              size="xs"
              class="square-button q-mr-sm"
            />
            <q-btn
              icon="o_delete"
              color="grey-4"
              text-color="primary"
              unelevated
              no-caps
              outline
              square
              size="xs"
              class="square-button"
            />
          </template>
          <template v-else>
            {{ renderCell(slotProps.row, col) }}
          </template>
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
import { useI18n } from 'vue-i18n';

const { t: $t } = useI18n();

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
  const baseCols = (props.columns ?? []).map((c) => ({
    name: c.key,
    label: c.unit ? `${c.label} (${c.unit})` : c.label,
    field: c.key,
    sortable: !!c.sortable,
    align: c.align ?? 'left',
  }));

  baseCols.push({
    name: 'action',
    label: $t('common_actions'), // Or use $t('common_actions') for translation
    field: 'action',
    align: 'right',
    sortable: false,
  });
  return baseCols;
});

function renderCell(row: ModuleRow, col: { field: string }) {
  const val = row[col.field];
  if (val === undefined || val === null) return '-';
  return String(val);
}
</script>
