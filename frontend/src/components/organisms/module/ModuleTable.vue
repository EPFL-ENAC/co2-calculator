<template>
  <div v-if="hasTopBar" class="q-mb-md flex justify-between items-center wrap">
    <div class="q-gutter-sm">
      <q-btn
        outline
        icon="o_view_list"
        color="primary"
        :label="$t('common_upload_csv')"
        unelevated
        no-caps
        size="sm"
        class="text-weight-medium"
        @click="onUploadCsv"
      />
      <q-btn
        icon="download"
        color="accent"
        :label="$t('common_download_csv_template')"
        unelevated
        no-caps
        size="sm"
        class="text-weight-medium"
        @click="onDownloadTemplate"
      />
      <q-icon
        :name="outlinedInfo"
        size="sm"
        class="cursor-pointer"
        :aria-label="
          $t(`${moduleType}-${submoduleType}-table-title-info-tooltip`)
        "
      />
      <q-tooltip anchor="center left" self="top right" class="u-tooltip">
        <p>
          {{ $t(`${moduleType}-${submoduleType}-table-title-info-tooltip`) }}
        </p>
      </q-tooltip>
    </div>
    <q-input
      v-model="filterTerm"
      dense
      outlined
      debounce="200"
      class="table-search"
      :placeholder="$t('common_search_placeholder') || 'Search'"
      clearable
      clear-icon="o_close"
      prefix-icon="o_search"
    >
      <template #prepend>
        <q-icon name="o_search" color="grey-6" size="16px" />
      </template>
    </q-input>
  </div>
  <q-table
    v-model:pagination="moduleStore.state.paginationSubmodule[submoduleType]"
    class="co2-table border"
    :columns="qCols"
    :rows="moduleStore.state.dataSubmodule[submoduleType]?.items || []"
    row-key="id"
    :loading="moduleStore.state.loadingSubmodule[submoduleType]"
    :error="moduleStore.state.errorSubmodule[submoduleType]"
    dense
    flat
    :hide-pagination="moduleconfig?.hasTablePagination === false"
    no-data-label="No items"
    :filter="filterTerm"
    @request="onRequest"
  >
    <template #header="scope">
      <q-tr :props="scope">
        <q-th
          v-for="col in scope.cols"
          :key="col.name"
          :props="scope"
          :align="col.align"
          class="q-pa-xs"
        >
          <span>{{ col.label }}</span>
          <q-icon
            v-if="col.tooltip"
            name="o_info"
            size="16px"
            color="grey-6"
            class="q-ml-xs"
          >
            <q-tooltip class="tooltip">{{ $t(col.tooltip) }}</q-tooltip>
          </q-icon>
        </q-th>
      </q-tr>
    </template>
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
      <q-tr
        :props="{ props: slotProps }"
        class="q-tr--no-hover"
        :class="rowClasses(slotProps.row)"
      >
        <q-td
          v-for="col in qCols"
          :key="col.name"
          :props="slotProps"
          :align="col.align"
          :class="cellClasses(slotProps.row, col)"
        >
          <template v-if="col.editableInline">
            <module-inline-select
              v-if="col.name === 'class' || col.name === 'sub_class'"
              :row="slotProps.row"
              :field-id="col.field"
              :module-type="moduleType"
              :submodule-type="submoduleType as any"
              :unit-id="unitId"
              :year="year"
            />
            <component
              :is="col.inputComponent"
              v-else
              v-model="slotProps.row[col.field]"
              :type="col.type === 'number' ? 'number' : undefined"
              :options="col.options || []"
              :dense="true"
              hide-bottom-space
              outlined
              :min="col.min"
              :max="col.max"
              :step="col.step"
              class="inline-input"
              :error="!!getError(slotProps.row, col)"
              :error-message="getError(slotProps.row, col)"
              @blur="commitInline(slotProps.row, col)"
            ></component>
          </template>
          <template
            v-else-if="
              col.name === 'action' &&
              props.moduleconfig.hasTableAction !== false
            "
          >
            <q-btn
              icon="o_delete"
              color="grey-4"
              text-color="primary"
              unelevated
              no-caps
              dense
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
            <div class="cell-content">
              <span>{{ renderCell(slotProps.row, col) }}</span>
              <q-badge
                v-if="col.name === 'name' && isNew(slotProps.row)"
                color="accent"
                class="q-ml-xs"
                rounded
                outline
                dense
                label="New"
              />
            </div>
          </template>
        </q-td>
      </q-tr>
    </template>

    <template #no-data>
      <div class="text-center q-pa-sm">No data available</div>
    </template>
  </q-table>

  <q-dialog v-model="editDialogOpen" persistent>
    <q-card style="width: 1320px; max-width: 90vw">
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
        <div class="q-pa-md text-body2 text-grey-7">
          {{
            $t('equipment_edit_disclaimer') ||
            "Pensez à mettre à jour votre inventaire : si vous ajoutez un élément manuellement cette année, il ne sera pas repris l’année prochaine, sauf si vous l’avez intégré dans votre inventaire. Your change won't be reflected in the DB. If you change power, contact us."
          }}
        </div>
        <module-form
          :fields="editInputs"
          :row-data="editRowData"
          :submodule-type="submoduleType"
          :module-type="moduleType"
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
import { computed, ref, watch, nextTick, onMounted } from 'vue';
import type { ModuleField } from 'src/constant/moduleConfig';
import { useI18n } from 'vue-i18n';
import ModuleForm from './ModuleForm.vue';
import ModuleInlineSelect from './ModuleInlineSelect.vue';
import { QInput, QSelect, useQuasar } from 'quasar';
import { useModuleStore } from 'src/stores/modules';
import { outlinedInfo } from '@quasar/extras/material-icons-outlined';
import type {
  Module,
  ConditionalSubmoduleProps,
  Threshold,
} from 'src/constant/modules';

import { MODULES } from 'src/constant/modules';

import { formatNumber } from 'src/utils/number';

const { t: $t } = useI18n();

const $q = useQuasar();

const editDialogOpen = ref(false);
const editInputs = ref<ModuleField[] | null>(null);
type FieldValue = string | number | boolean | null;
const editRowData = ref<Record<string, FieldValue> | null>(null);

type RowValue = string | number | boolean | null | undefined;
type ModuleRow = Record<string, RowValue> & {
  id: string | number;
  is_new?: boolean;
  status?: string;
};

type CommonProps = {
  moduleFields: ModuleField[] | null;
  unitId: string;
  year: string | number;
  threshold: Threshold;
  hasTopBar?: boolean;
  moduleconfig: {
    hasTableAction?: boolean;
    hasTopBar?: boolean;
    hasTablePagination?: boolean;
  };
};

type ModuleTableProps = ConditionalSubmoduleProps & CommonProps;

const props = withDefaults(defineProps<ModuleTableProps>(), {
  hasTopBar: true,
});

const moduleStore = useModuleStore();

const filterTerm = ref('');
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

const deleteItemName = ref<string>('');
const deleteRowId = ref<number | null>(null);

type TableViewColumn = {
  name: string;
  label: string;
  field: string;
  sortable: boolean;
  align: 'left' | 'right' | 'center';
  min?: number;
  max?: number;
  step?: number;
  inputComponent: typeof QInput | typeof QSelect;
  editableInline: boolean;
  options?: Array<{ value: string; label: string }>;
  tooltip?: string;
  type: ModuleField['type'];
};

const qCols = computed<TableViewColumn[]>(() => {
  const baseCols = (props.moduleFields ?? [])
    .filter((f) => !f.hideIn?.table)
    .map((f) => {
      const unit = f.unit;
      let labelText = unit ? `${f.label ?? ''} (${unit})` : (f.label ?? '');
      const i18nLabelKey = f.labelKey ?? '';
      if (i18nLabelKey) {
        // Use i18n label if available
        const translated = $t(i18nLabelKey);
        if (translated && translated !== i18nLabelKey) {
          // Only use if translation exists
          labelText = translated;
        }
      }
      const sortable = f.sortable ?? false;
      const align = f.align ?? 'left';
      const tooltip = f.tooltip;
      const readOnly = f.readOnly ?? false;
      const editableInline =
        !!(f.editableInline ?? false) &&
        !readOnly &&
        f.id !== 'act_power' &&
        f.id !== 'pas_power';
      const options = f.options ?? undefined;
      const inputComponent: typeof QInput | typeof QSelect =
        f.type === 'select' ? QSelect : QInput;
      return {
        name: f.id,
        label: labelText,
        field: f.id,
        sortable,
        min: f.min,
        max: f.max,
        step: f.step,
        align,
        inputComponent,
        editableInline,
        options,
        tooltip,
        type: f.type,
      };
    });

  if (props.moduleconfig.hasTableAction !== false) {
    baseCols.push({
      name: 'action',
      label: $t('common_actions'),
      field: 'action',
      align: 'right',
      sortable: false,
      inputComponent: QInput,
      min: undefined,
      max: undefined,
      step: undefined,
      editableInline: false,
      options: undefined,
      tooltip: undefined,
      type: 'text',
    });
  }
  return baseCols;
});

function renderCell(row: ModuleRow, col: { field: string; name: string }) {
  const val = row[col.field];
  if (val === undefined || val === null || val === '') return '-';
  if (col.name === 'kg_co2eq') {
    return formatNumber(val as number, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    });
  }
  if (typeof val === 'string') return val;
  if (typeof val === 'number') {
    return formatNumber(val);
  }
  console.warn('Unexpected cell value type', val);
  return String(val);
}

function getItemName(row: ModuleRow): string {
  return String(row?.name ?? row?.display_name ?? $t('common_this_item'));
}

function getRowId(row: ModuleRow): number | null {
  const n = Number(row.id);
  return Number.isFinite(n) ? n : null;
}

const inlineErrors = ref<Record<string, string>>({});
function errorKey(row: ModuleRow, col: { name: string }) {
  return `${row.id}-${col.name}`;
}
function setError(row: ModuleRow, col: { name: string }, msg: string | null) {
  const key = errorKey(row, col);
  if (!msg) delete inlineErrors.value[key];
  else inlineErrors.value[key] = msg;
}
function getError(row: ModuleRow, col: { name: string }) {
  return inlineErrors.value[errorKey(row, col)] ?? '';
}

function validateUsage(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return { valid: false, parsed: null, error: 'Required' };
  }
  const n = Number(value);
  if (!Number.isFinite(n))
    return { valid: false, parsed: null, error: 'Number required' };
  if (n < 0) return { valid: false, parsed: null, error: 'Must be >= 0' };
  if (n > 168) return { valid: false, parsed: null, error: 'Max 168 hrs/wk' };
  return { valid: true, parsed: n, error: null };
}

async function commitInline(
  row: ModuleRow,
  col: { name: string; field: string; editableInline?: boolean },
) {
  if (!col.editableInline) return;
  // Only usage fields use the hours/week validation; other inline
  // fields (including selects) are patched as-is.
  const isUsageField = col.name === 'act_usage' || col.name === 'pas_usage';
  const rawVal = row[col.field];
  const valueToSave = (() => {
    if (!isUsageField) return rawVal;
    const validation = validateUsage(rawVal);
    if (!validation.valid) {
      setError(row, col, validation.error);
      return null;
    }
    setError(row, col, null);
    return validation.parsed;
  })();

  if (valueToSave === null) return;

  const moduleType = props.moduleType as Module;
  const store = useModuleStore();
  const id = getRowId(row);
  if (id == null) return;
  try {
    await store.patchItem(
      moduleType,
      props.submoduleType,
      props.unitId,
      String(props.year),
      id,
      {
        [col.field]: valueToSave,
      },
    );
  } catch (err) {
    setError(row, col, err instanceof Error ? err.message : 'Save failed');
  }
}

function rowClasses(row: ModuleRow) {
  return {
    'row-new': isNew(row),
    'row-incomplete': !isComplete(row),
  };
}

function cellClasses(row: ModuleRow, col: { name: string; field: string }) {
  if (col.name === 'kg_co2eq') {
    if (row.status && String(row.status).toLowerCase() !== 'in service')
      return '';
    const thresholdVal = props.threshold?.value ?? null;
    const val = Number(row[col.field]);
    if (thresholdVal !== null && Number.isFinite(val) && val > thresholdVal) {
      return 'text-negative';
    }
  }
  return '';
}

function isNew(row: ModuleRow) {
  return Boolean(row.is_new);
}

function isComplete(row: ModuleRow) {
  const required = [
    'name',
    'class',
    'act_usage',
    'pas_usage',
    'act_power',
    'pas_power',
  ];
  return required.every(
    (k) => row[k] !== null && row[k] !== undefined && row[k] !== '',
  );
}

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

  // Normalize class value
  const classValRaw = payload.class as string | { value?: string } | null;
  const classValCandidate =
    classValRaw && typeof classValRaw === 'object'
      ? (classValRaw.value ?? '')
      : (classValRaw ?? '');
  const classVal = classValCandidate ? String(classValCandidate) : '';

  const basePayload: Record<string, FieldValue> = {
    ...payload,
    class: classVal,
  };

  const perform = async () => {
    // Backend will auto-resolve power_factor_id and power values
    // based on class/sub_class, so no need to fetch them here
    basePayload.act_usage = Number(payload.act_usage);
    basePayload.pas_usage = Number(payload.pas_usage);

    const p = isEdit
      ? store.patchItem(
          moduleType,
          props.submoduleType,
          unit,
          year,
          equipmentId,
          basePayload,
        )
      : store.postItem(
          moduleType,
          unit,
          year,
          props.submoduleType,
          basePayload,
        );

    await p.finally(() => {
      editDialogOpen.value = false;
      editRowData.value = null;
    });
  };

  perform();
}

function onUploadCsv() {
  $q.notify({
    color: 'info',
    message: $t('common_upload_csv_mock') || 'CSV upload coming soon (mocked)',
    position: 'top',
  });
}

function onDownloadTemplate() {
  // Mocked download
  const csvEquipmentContent =
    'Name,Class,SubClass,Active power (W),Standby power (W),Active usage (hrs/week),Passive usage (hrs/week)\n' +
    'Example Equipment,Example Class,Example Subclass,100,10,40,128';

  const csvHeadcountContent =
    'Position,Full-Time Equivalent (FTE)\n' + 'Researcher,5\n' + 'Technician,3';

  const csvContent =
    props.moduleType === MODULES.MyLab
      ? csvHeadcountContent
      : csvEquipmentContent;

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const csvUrl = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = csvUrl;
  a.download = `${props.moduleType}-template.csv`; // filename for the user
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  $q.notify({
    color: 'info',
    message:
      $t('common_download_csv_template_mock') ||
      'CSV template download (mocked)',
    position: 'top',
  });
}

function onConfirmDelete() {
  const store = useModuleStore();
  if (deleteRowId.value == null) {
    confirmDelete.value = false;
    return;
  }
  const moduleType = props.moduleType as Module;
  const submoduleType = props.submoduleType;
  const unit = props.unitId;
  const year = String(props.year);
  store
    .deleteItem(moduleType, submoduleType, unit, year, deleteRowId.value)
    .finally(() => {
      confirmDelete.value = false;
      deleteRowId.value = null;
    });
}

async function onRequest(request: {
  pagination: {
    page: number;
    rowsPerPage: number;
    rowsNumber?: number;
    sortBy?: string;
    descending?: boolean;
  };
  filter?: string;
}) {
  // Server-side pagination: check what changed
  const pagination = moduleStore.state.paginationSubmodule[props.submoduleType];
  const currentSortBy = pagination.sortBy;
  const currentSortOrder = pagination.descending;
  const newSortBy = request.pagination.sortBy;
  const newSortOrder = request.pagination.descending;
  // Check if sort changed (sort changes take priority and typically reset to page 1)
  const sortChanged =
    newSortBy &&
    (newSortBy !== currentSortBy || newSortOrder !== currentSortOrder);
  moduleStore.state.paginationSubmodule[props.submoduleType] =
    request.pagination;

  moduleStore.state.filterTermSubmodule[props.submoduleType] =
    request.filter || '';
  if (sortChanged) {
    // When sort changes, reset to page 1
    await moduleStore.getSubmoduleData({
      submoduleType: props.submoduleType,
      moduleType: props.moduleType,
      unit: props.unitId,
      year: String(props.year),
    });
  } else {
    // Only change page if sort didn't change
    await moduleStore.getSubmoduleData({
      submoduleType: props.submoduleType,
      moduleType: props.moduleType,
      unit: props.unitId,
      year: String(props.year),
    });
  }
}

watch(
  () => moduleStore.state.expandedSubmodules[props.submoduleType],
  (isExpanded) => {
    if (isExpanded) {
      moduleStore.initializeSubmoduleState(props.submoduleType);

      // table-specific work
      moduleStore.getSubmoduleData({
        submoduleType: props.submoduleType,
        moduleType: props.moduleType,
        unit: props.unitId,
        year: String(props.year),
      });
      // or recompute columns, resize, etc.
    }
  },
);

onMounted(() => {
  moduleStore.initializeSubmoduleState(props.submoduleType);
  // Clear inline errors on mount
  inlineErrors.value = {};
});
</script>

<style scoped lang="scss">
.table-search {
  min-width: 240px;
}

.inline-input {
  width: 120px;
}

.row-new {
  border-left: 4px solid #f2c037;
}

.row-incomplete {
  background: #fff4e5;
}

.cell-content {
  display: inline-flex;
  align-items: center;
}

.tooltip {
  max-width: 280px;
  white-space: normal;
}
</style>
