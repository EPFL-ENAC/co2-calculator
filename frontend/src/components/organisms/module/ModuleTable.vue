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
    <div>
      <q-btn
        icon="o_add_circle"
        color="accent"
        :label="$t('common_add_button')"
        unelevated
        no-caps
        size="sm"
        class="text-weight-medium"
        @click="openCreateDialog"
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
              @click="openEditDialog(slotProps.row)"
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
                ItemName = getItemName(slotProps.row);
                deleteItemName = getItemName(slotProps.row);
                deleteRowId = getRowId(slotProps.row);
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

  <q-dialog v-model="editDialogOpen" persistent>
    <q-card style="width: 1200px; max-width: 90vw">
      <q-card-section class="flex justify-between items-center">
        <div class="text-h4 text-weight-medium">
          {{
            $t('common_edit_dialog_title', {
              item: ItemName || 'this item',
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
      <q-card-section class="q-pa-none">
        <ModuleForm
          :inputs="editInputs"
          :row-data="editRowData"
          @submit="onFormSubmit"
          @edit="editDialogOpen = false"
        />
      </q-card-section>
    </q-card>
  </q-dialog>

  <q-dialog v-model="confirmDelete" class="modal modal--md" persistent>
    <q-card class="column">
      <q-card-section class="flex justify-between items-center">
        <div class="text-h4 text-weight-medium">
          {{
            $t('common_delete_dialog_title', {
              item: ItemName || 'this item',
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
              item: ItemName || 'this item',
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
          @click="onConfirmDelete"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import type { TableColumn, FormInput } from 'src/constant/moduleConfig';
import { useI18n } from 'vue-i18n';
import ModuleForm from './ModuleForm.vue';
import { QInput, QSelect } from 'quasar';
import { useModuleStore } from 'src/stores/modules';
import type { Module } from 'src/constant/modules';

const { t: $t } = useI18n();

const editDialogOpen = ref(false);
const editInputs = ref<FormInput[] | null>(null);
type FieldValue = string | number | boolean | null;
const editRowData = ref<Record<string, FieldValue> | null>(null);

type RowValue = string | number | boolean | null | undefined;
type ModuleRow = Record<string, RowValue> & { id: string | number };

const props = defineProps<{
  columns?: TableColumn[] | null;
  rows?: ModuleRow[];
  loading?: boolean;
  error?: string | null;
  formInputs?: FormInput[] | null;
  moduleType: Module | string;
  unitId: string;
  year: string | number;
}>();

const pagination = ref({
  page: 1,
  rowsPerPage: 20,
});

const confirmDelete = ref(false);
const ItemName = ref<string>('');

// Reset editRowData after dialog closes to prevent layout shift
watch(editDialogOpen, (isOpen) => {
  if (!isOpen) {
    nextTick(() => {
      editRowData.value = null;
      editInputs.value = null;
    });
  }
});

// Component map to convert strings to component references
const componentMap = {
  QInput,
  QSelect,
};
const deleteItemName = ref<string>('');
const deleteRowId = ref<number | null>(null);

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

// function mapRowDataToFormInputs(
//   row: ModuleRow,
//   columns: TableColumn[] | null | undefined,
//   formInputs: FormInput[] | null | undefined,
// ): Record<string, RowValue> {
//   if (!formInputs || !columns) return { ...row };

//   const mapped: Record<string, RowValue> = {};

//   formInputs.forEach((formInput) => {
//     // Try direct match first
//     if (row[formInput.id] !== undefined) {
//       mapped[formInput.id] = row[formInput.id];
//       return;
//     }

//     // Find column where form input ID ends with column key (e.g., 'sci_name' -> 'name')
//     const col = columns.find((c) => formInput.id.endsWith(`_${c.key}`));
//     if (col && row[col.key] !== undefined) {
//       mapped[formInput.id] = row[col.key];
//     }
//   });

//   return mapped;
// }

function onFormSubmit(
  payload: Record<string, string | number | boolean | null>,
) {
  const store = useModuleStore();
  const moduleType = props.moduleType as Module;
  const unit = props.unitId;
  const year = String(props.year);
  const idRaw = editRowData.value?.id;
  const equipmentId = Number(idRaw);
  const isEdit = Number.isFinite(equipmentId);
  payload.act_usage = Number(payload.act_usage);
  payload.pas_usage = Number(payload.pas_usage);
  const p = isEdit
    ? store.updateEquipment(moduleType, unit, year, equipmentId, payload)
    : store.createEquipment(moduleType, unit, year, payload);

  p.finally(() => {
    editDialogOpen.value = false;
    editRowData.value = null;
  });
}

function openEditDialog(row: ModuleRow) {
  editRowData.value = row;
  editInputs.value =
    props.columns?.map((c) => ({
      id: c.key,
      label: c.label,
      type: 'text',
      required: false,
    })) || null;
  editDialogOpen.value = true;
}

// function openEditDialog(row: ModuleRow) {
//   ItemName.value = getItemName(row);
//   // Set inputs first, then rowData, so form initializes correctly
//   editInputs.value = props.formInputs || null;
//   // Map row data keys to form input IDs
//   editRowData.value = mapRowDataToFormInputs(
//     row,
//     props.columns,
//     props.formInputs,
//   );
// }

function openCreateDialog() {
  editRowData.value = null;
  editInputs.value =
    props.columns?.map((c) => ({
      id: c.key,
      label: c.label,
      type: 'text',
      required: false,
    })) || null;
  editDialogOpen.value = true;
}

function getItemName(row: ModuleRow): string {
  return row.name ? String(row.name) : String(row.id || 'this item');
}

function getRowId(row: ModuleRow): number | null {
  const n = Number(row.id);
  return Number.isFinite(n) ? n : null;
}

function onConfirmDelete() {
  const store = useModuleStore();
  if (deleteRowId.value == null) {
    confirmDelete.value = false;
    return;
  }
  const moduleType = props.moduleType as Module;
  const unit = props.unitId;
  const year = String(props.year);
  store
    .deleteEquipment(moduleType, unit, year, deleteRowId.value)
    .finally(() => {
      confirmDelete.value = false;
      deleteRowId.value = null;
    });
}
</script>
