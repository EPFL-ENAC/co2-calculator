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
    :pagination="pagination"
  >
    <template #pagination="scope">
      <q-btn
        icon="chevron_left"
        color="grey-8"
        round
        dense
        flat
        :disable="scope.isFirstPage"
        @click="scope.prevPage"
      />

      <q-btn
        icon="chevron_right"
        color="grey-8"
        round
        dense
        flat
        :disable="scope.isLastPage"
        @click="scope.nextPage"
      />
    </template>
    <template #body="slotProps">
      <q-tr :props="{ props: slotProps }" class="q-tr--no-hover">
        <q-td
          v-for="col in qCols"
          :key="col.name"
          :props="slotProps"
          :align="col.align"
        >
          <template v-if="col.editableInline">
            <component
              :is="col.inputComponent"
              v-model="slotProps.row[col.field]"
              :options="col.options || []"
              dense
              hide-bottom-space
              outlined
              class="inline-input"
            ></component>
          </template>
          <template v-else-if="col.name === 'action'">
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
              @click="
                deleteItemName = getItemName(slotProps.row);
                confirmDelete = true;
              "
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

  <q-dialog v-model="confirmDelete" persistent>
    <q-card class="column modal modal--md">
      <q-card-section class="flex justify-between items-center">
        <div class="text-h4 text-weight-medium">
          {{
            $t('common_delete_dialog_title', {
              item: deleteItemName || 'this item',
            })
          }}
        </div>
        <q-btn
          v-close-popup
          flat
          size="md"
          icon="o_close"
          color="grey-6"
          class="text-weight-medium"
        />
      </q-card-section>
      <q-separator />
      <q-card-section class="q-py-lg q-px-md">
        <span class="text-body1">
          {{
            $t('common_delete_dialog_description', {
              item: deleteItemName || 'this item',
            })
          }}
        </span>
      </q-card-section>
      <q-separator />
      <q-card-actions class="q-py-lg q-px-md row q-gutter-sm">
        <q-btn
          color="grey-4"
          text-color="primary"
          :label="$t('common_cancel')"
          unelevated
          no-caps
          outline
          size="md"
          class="text-weight-medium col"
          @click="confirmDelete = false"
        />
        <q-btn
          color="accent"
          :label="$t('common_delete')"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium col"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import type { TableColumn } from 'src/constant/moduleConfig';
import { useI18n } from 'vue-i18n';
import { QInput, QSelect } from 'quasar';

const { t: $t } = useI18n();

type RowValue = string | number | boolean | null | undefined;
type ModuleRow = Record<string, RowValue> & { id: string | number };

const props = defineProps<{
  columns?: TableColumn[] | null;
  rows?: ModuleRow[];
  loading?: boolean;
  error?: string | null;
}>();

const pagination = ref({
  page: 1,
  rowsPerPage: 20,
});

const confirmDelete = ref(false);
const deleteItemName = ref<string>('');

// Component map to convert strings to component references
const componentMap = {
  QInput,
  QSelect,
};

// simple local rows by default (can be passed via prop)
// const rows = ref(props.rows ?? []);

const qCols = computed(() => {
  const baseCols = (props.columns ?? []).map((c) => ({
    name: c.key,
    label: c.unit ? `${c.label} (${c.unit})` : c.label,
    field: c.key,
    sortable: !!c.sortable,
    align: c.align ?? 'left',
    inputComponent: c.inputTypeName ? componentMap[c.inputTypeName] : QInput,
    editableInline: !!c.editableInline,
    options: c.options || undefined,
  }));

  baseCols.push({
    name: 'action',
    label: $t('common_actions'), // Or use $t('common_actions') for translation
    field: 'action',
    align: 'right',
    sortable: false,
    inputComponent: QInput,
    editableInline: false,
    options: undefined,
  });
  return baseCols;
});

function renderCell(row: ModuleRow, col: { field: string }) {
  const val = row[col.field];
  if (val === undefined || val === null) return '-';
  return String(val);
}

function getItemName(row: ModuleRow): string {
  return row.name ? String(row.name) : String(row.id || 'this item');
}
</script>
