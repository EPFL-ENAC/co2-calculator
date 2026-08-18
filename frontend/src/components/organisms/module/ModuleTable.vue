<template>
  <div v-if="hasTopBar" class="q-mb-md flex justify-between items-center wrap">
    <div
      v-if="
        hasModuleUpload &&
        !isInputDeactivated &&
        canUseCsvTools &&
        !isCsvDeactivated
      "
      class="q-gutter-sm"
    >
      <q-btn
        outline
        icon="o_view_list"
        color="primary"
        :label="$t('common_upload_csv')"
        unelevated
        no-caps
        size="sm"
        class="text-weight-medium"
        :disable="isDisabled"
        @click="onUploadCsv"
      />
      <q-btn
        outline
        icon="o_download"
        color="primary"
        :label="$t('common_download_csv_template')"
        unelevated
        no-caps
        size="sm"
        class="text-weight-medium"
        :disable="isDisabled"
        @click="onDownloadTemplate"
      />

      <files-upload-dialog
        v-model="showUploadDialog"
        @files-uploaded="onFilesUploaded"
      />
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
  <!-- #259: new equipment (vs previous year) still missing usage data must be
       filled before the module can be validated. Sits below the CSV toolbar. -->
  <q-banner
    v-if="newEquipmentIncompleteCount > 0"
    dense
    rounded
    class="equipment-new-banner q-mb-md"
  >
    <template #avatar>
      <q-icon name="o_warning" class="equipment-new-banner__icon" />
    </template>
    {{
      $t('equipment_new_usage_required_banner', {
        count: newEquipmentIncompleteCount,
      })
    }}
  </q-banner>
  <q-table
    v-model:pagination="moduleStore.state.paginationSubmodule[submoduleType]"
    class="co2-table border"
    :class="{ 'co2-table--wrap-headers': projectYearsCount != null }"
    :style="tableStyle"
    :columns="qCols"
    :rows="moduleStore.state.dataSubmodule[submoduleType]?.items || []"
    row-key="id"
    :loading="moduleStore.state.loadingSubmodule[submoduleType]"
    :error="moduleStore.state.errorSubmodule[submoduleType]"
    dense
    flat
    :rows-per-page-options="ROWS_PER_PAGE_OPTIONS"
    :hide-pagination="submoduleConfig?.hasTablePagination === false"
    :no-data-label="$t('common_no_items')"
    :rows-per-page-label="$t('rows_per_page')"
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
          :class="{
            'column-max-width': col.maxColumnWidth !== undefined,
            'column-min-width':
              col.minColumnWidth !== undefined || col.columnSize !== undefined,
          }"
          :style="getColumnStyle(col)"
        >
          <span>{{ col.label }}</span>
          <q-icon
            v-if="col.tooltip && $t(col.tooltip)"
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
      <div v-if="scope.pagesNumber > 1" class="q-px-sm">
        {{ scope.pagination.page }} / {{ scope.pagesNumber }}
      </div>
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
          :class="getColumnClasses(slotProps.row, col)"
          :style="getColumnStyle(col)"
        >
          <template v-if="col.editableInline">
            <template
              v-if="
                isRowConditionallyReadOnly(slotProps.row, col) ||
                isRowFieldPolicyLocked(slotProps.row, col)
              "
            >
              <span>{{ renderReadOnlyInlineCell(slotProps.row, col) }}</span>
            </template>
            <module-inline-select
              v-else-if="
                col.optionsId === 'kind' || col.optionsId === 'subkind'
              "
              :row="slotProps.row"
              :field-id="col.field"
              :options-id="col.optionsId"
              :option-label-key="col.optionLabelKey"
              :option-label-prefix="col.optionLabelPrefix"
              :option-order="col.optionOrder"
              :cols="qCols"
              :module-type="moduleType"
              :submodule-type="submoduleType as any"
              :hint="col.hint"
              :unit-id="unitId"
              :year="year"
              :factor-year="factorYear"
              :disable="isDisabled"
            />
            <component
              :is="col.inputComponent"
              v-else
              v-model="slotProps.row[col.field]"
              :disable="isDisabled"
              :inputmode="getColumnInputmode(col)"
              :options="getInlineOptions(col)"
              :dense="true"
              hide-bottom-space
              emit-value
              map-options
              outlined
              :title="getColumnTitle(col)"
              :min="col.min"
              :max="col.max"
              :step="col.step"
              :rules="getColumnRules(col)"
              :placeholder="
                isRequiredEmptyUsageCell(slotProps.row, col) ? '—' : undefined
              "
              :class="[
                'inline-input',
                {
                  'inline-input--required-empty': isRequiredEmptyUsageCell(
                    slotProps.row,
                    col,
                  ),
                },
              ]"
              :dropdown-icon="col.type === 'select' ? 'expand_more' : undefined"
              :error="!!getError(slotProps.row, col)"
              :error-message="getError(slotProps.row, col)"
              @blur="col.type !== 'select' && commitInline(slotProps.row, col)"
              @update:model-value="
                col.type === 'select' && commitInline(slotProps.row, col)
              "
            >
              <template v-if="col.type !== 'select'" #append>
                <q-icon
                  v-if="hasValue(slotProps.row[col.field])"
                  name="o_edit"
                  size="14px"
                  class="inline-edit-icon"
                />
              </template>
            </component>
          </template>
          <template v-else-if="col.name === 'action' && showTableActions">
            <q-btn
              v-if="showTableNote"
              :icon="noteButtonIcon(slotProps.row.note)"
              :color="noteButtonColor(slotProps.row.note)"
              :style="noteButtonStyle(slotProps.row.note)"
              :disable="isNoteDisabled"
              unelevated
              no-caps
              dense
              :flat="!slotProps.row.note"
              class="action-btn"
              @click="openNoteDialog(slotProps.row)"
            >
              <q-tooltip v-if="slotProps.row.note" class="tooltip">
                {{ slotProps.row.note }}
              </q-tooltip>
              <q-tooltip v-else class="tooltip action-tooltip" :offset="[0, 8]">
                {{ $t('common_comment') }}
              </q-tooltip>
            </q-btn>
            <q-btn
              v-if="showTableRowActions && canEditRows && hasModuleUpload"
              icon="o_delete"
              color="black"
              :disable="isDisabled || !isRowPolicyDeletable(slotProps.row)"
              unelevated
              no-caps
              dense
              flat
              class="action-btn action-btn--delete"
              @click="
                ItemName = getItemName(slotProps.row);
                deleteItemName = getItemName(slotProps.row);
                deleteRowId = getRowId(slotProps.row);
                confirmDelete = true;
              "
            >
              <q-tooltip class="tooltip action-tooltip" :offset="[0, 8]">
                {{ $t('common_delete') }}
              </q-tooltip>
            </q-btn>
          </template>
          <template v-else-if="col.name === 'percentage_of_reference_year'">
            <div
              v-if="slotProps.row.reference_kg_co2eq != null"
              class="row items-center no-wrap reference-slider"
            >
              <q-slider
                :model-value="percentageOf(slotProps.row)"
                :min="REFERENCE_PERCENTAGE_MIN"
                :max="REFERENCE_PERCENTAGE_MAX"
                :step="5"
                :disable="isDisabled || percentageLocked"
                color="negative"
                class="col"
                @update:model-value="
                  (val: number | null) => onPercentageDrag(slotProps.row, val)
                "
                @change="
                  (val: number) => onPercentageChange(slotProps.row, val)
                "
              />
              <div class="reference-slider__value">
                <q-input
                  :key="percentageInputKey(slotProps.row)"
                  :model-value="percentageOf(slotProps.row)"
                  type="number"
                  :min="REFERENCE_PERCENTAGE_MIN"
                  :max="REFERENCE_PERCENTAGE_MAX"
                  :disable="isDisabled || percentageLocked"
                  :aria-label="$t('planner_percentage_col')"
                  :style="percentageFieldWidth(slotProps.row)"
                  dense
                  borderless
                  hide-bottom-space
                  class="reference-slider__field"
                  @update:model-value="
                    (val: string | number | null) =>
                      onPercentageTyped(slotProps.row, val)
                  "
                  @blur="() => commitPercentage(slotProps.row)"
                  @keyup.enter="() => commitPercentage(slotProps.row)"
                />
                <span class="reference-slider__unit" aria-hidden="true">%</span>
              </div>
            </div>
            <span v-else>-</span>
          </template>
          <template v-else>
            <div class="cell-content">
              <span>{{ renderCell(slotProps.row, col) }}</span>
              <q-badge
                v-if="col.name === 'name' && isNewIncomplete(slotProps.row)"
                class="q-ml-md badge-new"
                rounded
                outline
                dense
                :label="$t('common_new')"
              />
            </div>
          </template>
        </q-td>
      </q-tr>
    </template>

    <template #no-data>
      <div class="text-center q-pa-sm">
        {{ $t('common_no_data_available') }}
      </div>
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

  <NoteDialog
    v-model="noteDialogOpen"
    :note="noteDialogCurrentNote"
    :mode="noteDialogMode"
    :module-color="moduleColors.bgColorLighter"
    :module-text-color="moduleColors.buttonTextColor"
    @save="saveNote"
    @delete="deleteNote"
  />

  <EquipmentPowerFeedbackDialog
    v-model="powerFeedbackDialogOpen"
    :note="noteDialogCurrentNote"
    :mode="noteDialogMode"
    :equipment-name="powerFeedbackRow.equipmentName"
    :equipment-class="powerFeedbackRow.equipmentClass"
    :sub-class="powerFeedbackRow.subClass"
    :current-active-power-w="powerFeedbackRow.currentActivePowerW"
    :current-standby-power-w="powerFeedbackRow.currentStandbyPowerW"
    :unit-name="powerFeedbackUnitName"
    :year="year"
    :module-color="moduleColors.bgColorLighter"
    :module-text-color="moduleColors.buttonTextColor"
    :module-accent-color="moduleColors.borderColor"
    @save="saveNote"
    @delete="deleteNote"
  />

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
      <!-- q-form so Enter submits the dialog (autofocus on the submit button
           gives the native form an Enter target — there are no text inputs). -->
      <q-form @submit.prevent="onConfirmDelete">
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
            type="button"
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
            type="submit"
            autofocus
            :style="{
              background: moduleColors.bgColorLighter,
              color: moduleColors.buttonTextColor,
              border: `1px solid ${moduleColors.buttonTextColor}`,
            }"
            :label="$t('common_delete')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium col"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import FilesUploadDialog from 'src/components/organisms//data-management/FilesUploadDialog.vue';

import { computed, ref, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { COLUMN_SIZES } from 'src/constant/moduleConfig';
import type {
  ModuleField,
  ModuleConfig,
  Submodule,
} from 'src/constant/moduleConfig';
import { useI18n } from 'vue-i18n';
import ModuleForm from './ModuleForm.vue';
import ModuleInlineSelect from './ModuleInlineSelect.vue';
import NoteDialog from 'src/components/molecules/NoteDialog.vue';
import EquipmentPowerFeedbackDialog from 'src/components/molecules/EquipmentPowerFeedbackDialog.vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import { QInput, QSelect, useQuasar } from 'quasar';
import { useModuleStore, useTimelineStore } from 'src/stores/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useAuthStore } from 'src/stores/auth';
import {
  useBackofficeDataManagement,
  TargetType,
} from 'src/stores/backofficeDataManagement';
import type { JobUpdatePayload } from 'src/stores/backofficeDataManagement';
import { PermissionAction } from 'src/stores/auth';
import { getTemplateFileName } from 'src/constant/templateMapping';
import { INSTITUTIONAL_ID_LABEL } from 'src/constant/institutionalId';
import { CARBON_PROJECT } from 'src/constant/carbon-project';
import { resolveTravelerCellText } from 'src/constant/module-config/traveler-options';
import type {
  Module,
  ConditionalSubmoduleProps,
  Threshold,
  EnumSubmoduleType,
} from 'src/constant/modules';
import { enumSubmodule, SUBMODULE_PURCHASE_TYPES } from 'src/constant/modules';

import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  SUBMODULE_EXTERNAL_CLOUD_TYPES,
} from 'src/constant/modules';
import {
  getHeadcountMembers,
  type HeadcountMemberDropdownItem,
} from 'src/api/modules';
import { getModuleTypeId, MODULE_STATES } from 'src/constant/moduleStates';
import { nOrDash } from 'src/utils/number';
import { getModuleIconColors } from 'src/composables/useModuleIconColors';
import { formatRowErrorLines } from 'src/utils/rowErrors';
import { isFieldEditable, isRowDeletable } from 'src/utils/dataEntryPolicy';
import {
  clampReferencePercentage,
  REFERENCE_PERCENTAGE_MAX,
  REFERENCE_PERCENTAGE_MIN,
} from 'src/utils/reference-percentage';
import {
  hasRowEditPermission,
  isModuleNoteDisabled,
  isModuleTableDisabled,
  type ModuleTableAccess,
} from 'src/utils/module-table-access';

function getNumericRules(col: TableViewColumn) {
  const rules = [];

  rules.push((val: string | number | null) => {
    if (val === '' || val === null || val === undefined) return true;
    const s = typeof val === 'string' ? val.trim() : String(val);
    if (s.includes(',')) return $t('validation_use_dot_not_comma');
    return /^-?\d+(\.\d+)?$/.test(s) || $t('validation_number_format');
  });

  if (col.min !== undefined) {
    rules.push((val: string | number | null) => {
      const num = Number(val);
      return (
        num >= col.min! || $t('validation_must_be_at_least', { min: col.min })
      );
    });
  }

  if (col.max !== undefined) {
    rules.push((val: string | number | null) => {
      const num = Number(val);
      return (
        num <= col.max! || $t('validation_must_be_at_most', { max: col.max })
      );
    });
  }

  return rules;
}

const { t: $t, te: $te } = useI18n();

const $q = useQuasar();
const authStore = useAuthStore();
const dataManagementStore = useBackofficeDataManagement();

const headcountMembersMap = ref<Map<string, string>>(new Map());

const noteDialogOpen = ref(false);
const noteDialogCurrentNote = ref('');
const noteDialogRowId = ref<number | null>(null);

// The per-row Comment button. For Equipment (issue #266) it opens a 2-tab dialog
// (Comment + "Demande de modification de puissance") that can email a power-change
// request to the business admin, who edits the reference Factor manually. Other
// modules keep the plain NoteDialog. Both share the same note state so saving a
// comment persists identically.
const workspaceStore = useWorkspaceStore();
const isEquipmentModule = computed(
  () => props.moduleType === MODULES.Equipment,
);
const powerFeedbackDialogOpen = ref(false);
const powerFeedbackRow = ref<{
  equipmentName: string;
  equipmentClass: string;
  subClass: string | null;
  currentActivePowerW: number | null;
  currentStandbyPowerW: number | null;
}>({
  equipmentName: '',
  equipmentClass: '',
  subClass: null,
  currentActivePowerW: null,
  currentStandbyPowerW: null,
});
const powerFeedbackUnitName = computed(
  () => workspaceStore.selectedUnit?.name ?? String(props.unitId),
);

function openNoteDialog(row: ModuleRow) {
  noteDialogRowId.value = getRowId(row);
  noteDialogCurrentNote.value = (row.note as string) ?? '';
  if (isEquipmentModule.value) {
    powerFeedbackRow.value = {
      equipmentName: (row.name as string) ?? '',
      equipmentClass: (row.equipment_class as string) ?? '',
      subClass: (row.sub_class as string) ?? null,
      currentActivePowerW: (row.active_power_w as number) ?? null,
      currentStandbyPowerW: (row.standby_power_w as number) ?? null,
    };
    powerFeedbackDialogOpen.value = true;
    return;
  }
  noteDialogOpen.value = true;
}

async function saveNote(note: string) {
  if (noteDialogRowId.value == null) return;
  try {
    await moduleStore.patchItem(
      props.moduleType as Module,
      props.submoduleType,
      props.unitId,
      String(props.year),
      noteDialogRowId.value,
      { note },
      props.carbonReportId,
    );
  } catch {
    $q.notify({
      color: 'negative',
      message: $t('common_save_error'),
      position: 'top',
    });
  } finally {
    noteDialogRowId.value = null;
  }
}

async function deleteNote() {
  if (noteDialogRowId.value == null) return;
  try {
    await moduleStore.patchItem(
      props.moduleType as Module,
      props.submoduleType,
      props.unitId,
      String(props.year),
      noteDialogRowId.value,
      { note: null },
      props.carbonReportId,
    );
  } catch {
    $q.notify({
      color: 'negative',
      message: $t('common_save_error'),
      position: 'top',
    });
  } finally {
    noteDialogRowId.value = null;
  }
}
const ROWS_PER_PAGE_OPTIONS = [10, 20, 50, 100, 200, 1000];

const showUploadDialog = ref<boolean>(false);

const formatRowErrors = (payload?: JobUpdatePayload): string | undefined => {
  const lines = formatRowErrorLines(
    payload?.meta?.row_errors,
    payload?.meta?.row_errors_count,
    $t,
  );
  return lines.length === 0 ? undefined : lines.join('\n');
};

const onFilesUploaded = async (filePaths: string[]) => {
  showUploadDialog.value = false;

  if (!filePaths || filePaths.length === 0) {
    $q.notify({
      color: 'negative',
      message: $t('csv_no_files_uploaded'),
      position: 'top',
    });
    return;
  }

  const filePath = filePaths[0];
  const moduleTypeId = getModuleTypeId(props.moduleType as Module);

  try {
    $q.notify({
      color: 'info',
      message: $t('csv_sync_starting'),
      position: 'top',
    });
    const carbonReportModuleId =
      moduleStore.state.data?.carbon_report_module_id;
    const jobId = await dataManagementStore.initiateSync({
      module_type_id: moduleTypeId,
      year: Number(props.year),
      provider_type: 'csv',
      target_type: TargetType.DATA_ENTRIES,
      file_path: filePath,
      carbon_report_module_id: carbonReportModuleId,
      config: {
        carbon_report_module_id: carbonReportModuleId,
        data_entry_type_id:
          enumSubmodule[props.submoduleType as EnumSubmoduleType],
      },
    });

    dataManagementStore.subscribeToJobUpdates(
      jobId,
      (payload?: JobUpdatePayload) => {
        moduleStore.getSubmoduleData({
          submoduleType: props.submoduleType,
          moduleType: props.moduleType,
          unit: props.unitId,
          year: String(props.year),
          carbonReportId: props.carbonReportId,
        });
        moduleStore.getModuleData(
          props.moduleType as Module,
          props.unitId,
          String(props.year),
          props.carbonReportId,
        );

        const errorCaption = formatRowErrors(payload);
        if (errorCaption) {
          const totalErrorCount =
            payload?.meta?.row_errors_count ??
            payload?.meta?.row_errors?.length ??
            0;
          $q.notify({
            color: 'negative',
            message: $t('csv_sync_completed_with_errors', {
              count: totalErrorCount,
            }),
            caption: errorCaption,
            position: 'top',
            multiLine: true,
            timeout: 30000,
            actions: [
              {
                icon: 'o_report_problem',
                color: 'negative',
                textColor: 'white',
                label: $t('close_error_details'),
                handler: () => {
                  // Open a dialog or page to show detailed errors
                  // For simplicity, we'll just log them here
                  console.error(
                    'Detailed row errors:',
                    payload?.meta?.row_errors,
                  );
                },
                'aria-label': $t('close_error_details'),
              },
            ],
          });
        } else {
          $q.notify({
            color: 'positive',
            message: $t('csv_sync_completed'),
            position: 'top',
          });
        }
      },
      (payload?: JobUpdatePayload) => {
        $q.notify({
          color: 'negative',
          message: $t('csv_sync_failed'),
          caption: formatRowErrors(payload) || payload?.status_message || '',
          position: 'top',
          multiLine: true,
          timeout: 30000,
          actions: [
            {
              icon: 'o_report_problem',
              color: 'negative',
              textColor: 'white',
              label: $t('close_error_details'),
              handler: () => {
                // Open a dialog or page to show detailed errors
                // For simplicity, we'll just log them here
                console.error('Detailed row errors:', payload?.status_message);
              },
              'aria-label': $t('close_error_details'),
            },
          ],
        });
        console.error('CSV sync job failed:', payload);
      },
      () => {
        $q.notify({
          color: 'negative',
          message: $t('csv_sync_connection_lost'),
          position: 'top',
          timeout: 30000,
          closeBtn: true,
          actions: [
            {
              icon: 'close',
              // for individual action (button):
              'aria-label': 'Dismiss',
            },
          ],
        });
      },
    );
    $q.notify({
      color: 'positive',
      message: $t('csv_sync_initiated'),
      position: 'top',
    });
  } catch (err) {
    console.error('Failed to initiate sync:', err);
    $q.notify({
      color: 'negative',
      message:
        err instanceof Error ? err.message : $t('csv_sync_failed_to_initiate'),
      position: 'top',
    });
  }
};

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
  unitId: number;
  year: string | number;
  /** Year whose factors the class/subclass options resolve against — see ModuleForm. */
  factorYear?: number | null;
  /** Plan-year report id; when set, module calls address it directly. */
  carbonReportId?: number;
  /**
   * Planner prefilled context: add the reference-year kgCO₂eq column and the
   * 0–100% "% of reference year" slider (snapshot rows only). Off for the
   * Calculator and non-prefilled planner modules.
   */
  showReferenceColumns?: boolean;
  /**
   * Planner Project Grant context: the plan's year count. When set, the
   * kgCO₂eq column reads per-year and gains a "× project years" column after
   * it (#1979). Null everywhere else.
   */
  projectYearsCount?: number | null;
  /**
   * Grant equipment "global percentage" mode: the per-row % controls are
   * driven by the module-level value and stay read-only (#1981).
   */
  percentageLocked?: boolean;
  threshold: Threshold;
  hasTopBar?: boolean;
  moduleConfig: ModuleConfig;
  submoduleConfig: Submodule;
  disable: boolean;
  /** Simulator Explorer page — see `utils/module-table-access`. */
  isExplorer?: boolean;
  moduleColor?: string;
  moduleColorLighter?: string;
};

type ModuleTableProps = ConditionalSubmoduleProps & CommonProps;

const props = withDefaults(defineProps<ModuleTableProps>(), {
  hasTopBar: true,
  carbonReportId: undefined,
  factorYear: undefined,
  showReferenceColumns: false,
  projectYearsCount: null,
  percentageLocked: false,
  moduleColor: undefined,
  moduleColorLighter: undefined,
});
const moduleStore = useModuleStore();
const timelineStore = useTimelineStore();
const yearConfigStore = useYearConfigStore();

// #259: only the Equipment module reports new-vs-previous-year equipment still
// missing usage data; the banner warns the user before they try to validate.
const newEquipmentIncompleteCount = computed(() =>
  isEquipmentModule.value
    ? (moduleStore.state.data?.incomplete_new_equipment_count ?? 0)
    : 0,
);

const isInputDeactivated = computed(() => {
  const unifiedConfig = yearConfigStore.getModule(props.moduleType as Module);
  if (!unifiedConfig) return false;
  const subConfig = unifiedConfig.submodules[props.submoduleType as string];
  return subConfig?.inputs_deactivated ?? false;
});

const isCsvDeactivated = computed(() => {
  const unifiedConfig = yearConfigStore.getModule(props.moduleType as Module);
  if (!unifiedConfig) return false;
  const subConfig = unifiedConfig.submodules[props.submoduleType as string];
  return subConfig?.csv_deactivated ?? false;
});

const moduleColors = computed(() =>
  getModuleIconColors(String(props.moduleType), String(props.submoduleType)),
);

const tableStyle = computed(() =>
  props.moduleType === MODULES.Buildings
    ? {
        '--row-alt-color': '#f8fafc',
        '--table-header-bg': moduleColors.value.bgColorLighter,
      }
    : { '--row-alt-color': '#f8fafc' },
);

function noteButtonIcon(note: unknown): string {
  return note ? 'o_comment' : 'o_add_comment';
}

function noteButtonColor(note: unknown): string | undefined {
  if (!note) return 'black';
  return props.moduleColor ? undefined : 'accent';
}

function noteButtonStyle(note: unknown) {
  return note
    ? {
        background: moduleColors.value.bgColorLighter,
        color: moduleColors.value.buttonTextColor,
        border: `1px solid ${moduleColors.value.buttonTextColor}`,
      }
    : undefined;
}

const noteDialogMode = computed<'add' | 'edit'>(() =>
  noteDialogCurrentNote.value ? 'edit' : 'add',
);

function getColumnInputmode(col: TableViewColumn): string | undefined {
  // Text input + decimal inputmode (no native number type) so invalid keystrokes
  // stay in the cell instead of being silently dropped by the browser; the format
  // is validated on commit.
  return col.type === 'number' ? 'decimal' : undefined;
}

function getColumnTitle(col: TableViewColumn): string | undefined {
  return col.hint ? $t(col.hint) : undefined;
}

function getColumnRules(col: TableViewColumn) {
  return col.type === 'number' ? getNumericRules(col) : [];
}

const hasModuleUpload = computed(() => {
  return (
    props.moduleFields &&
    props.moduleFields.filter((field) => !field.hideIn?.form).length > 0
  );
});

const canUseCsvTools = computed(() =>
  authStore.hasUserCanValidateModuleStatus(),
);

// Permission check: can user edit this module?
const canEdit = computed(() => {
  return authStore.hasUserModulePermission(
    props.moduleType,
    PermissionAction.EDIT,
  );
});

// Planner tables address a plan-year report by id; the Calculator never does.
const tableAccess = computed<ModuleTableAccess>(() => ({
  isExplorer: props.isExplorer === true,
  isPlanner: props.carbonReportId != null,
  canEdit: canEdit.value,
  disable: props.disable === true,
  isValidated:
    timelineStore.itemStates[props.moduleType] === MODULE_STATES.Validated,
}));

const isDisabled = computed(() => isModuleTableDisabled(tableAccess.value));

// #951: null for submodules the policy layer doesn't cover (planner,
// embodied energy) — isFieldEditable/isRowDeletable treat null as ungated.
const dataEntryPolicies = computed(
  () =>
    moduleStore.state.dataSubmodule[props.submoduleType]?.data_entry_policies ??
    null,
);

function isRowFieldPolicyLocked(row: ModuleRow, col: { field: string }) {
  return !isFieldEditable(
    dataEntryPolicies.value,
    row.source as number | null | undefined,
    col.field,
  );
}

function isRowPolicyDeletable(row: ModuleRow) {
  return isRowDeletable(
    dataEntryPolicies.value,
    row.source as number | null | undefined,
  );
}

const canEditRows = computed(() => hasRowEditPermission(tableAccess.value));

const showTableRowActions = computed(
  () => props.submoduleConfig?.hasTableAction !== false,
);

const showTableNote = computed(
  () =>
    showTableRowActions.value || props.submoduleConfig?.hasTableNote === true,
);

const showTableActions = computed(() => showTableNote.value);

const isNoteDisabled = computed(() => isModuleNoteDisabled(tableAccess.value));

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
  hint?: string;
  min?: number;
  max?: number;
  step?: number;
  inputComponent: typeof QInput | typeof QSelect;
  editableInline: boolean;
  options?: Array<{ value: string; label: string }>;
  optionsId?: string;
  optionLabelKey?: string;
  tooltip?: string;
  type: ModuleField['type'];
  columnSize?: ModuleField['columnSize'];
  minColumnWidth?: number;
  maxColumnWidth?: number;
  readOnlyWhen?: ModuleField['readOnlyWhen'];
  readOnlyDisplayField?: string;
  optionLabelsAreKeys?: boolean;
  optionLabelPrefix?: string;
  optionOrder?: string[];
};

const qCols = computed<TableViewColumn[]>(() => {
  const baseCols: TableViewColumn[] = [];

  (props.moduleFields ?? [])
    .filter((f) => !f.hideIn?.table)
    .forEach((f) => {
      const unit = f.unit;
      const i18nLabelKey = f.labelKey ?? '';
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

      // If labelKey is an array, create one column per translation
      if (Array.isArray(i18nLabelKey)) {
        i18nLabelKey.forEach((labelKey, index) => {
          let labelText = unit ? `${f.label ?? ''} (${unit})` : (f.label ?? '');
          const translated = $t(labelKey, { unit });
          if (translated) {
            labelText = translated;
          }

          baseCols.push({
            name: `${f.id}_${index}`,
            label: labelText,
            field: f.id, // All columns use the same field
            sortable,
            hint: f.hint,
            min: f.min,
            max: f.max,
            step: f.step,
            align,
            inputComponent,
            editableInline,
            options,
            tooltip: index === 0 ? tooltip : undefined, // Only first column gets tooltip
            type: f.type,
            columnSize: f.columnSize,
            minColumnWidth: f.minColumnWidth,
            maxColumnWidth: f.maxColumnWidth,
            readOnlyWhen: f.readOnlyWhen,
            readOnlyDisplayField: f.readOnlyDisplayField,
            optionLabelsAreKeys: f.optionLabelsAreKeys,
            optionLabelPrefix: f.optionLabelPrefix,
            optionOrder: f.optionOrder,
          });
        });
      } else {
        // Single labelKey - create one column
        let labelText = unit ? `${f.label ?? ''} (${unit})` : (f.label ?? '');
        if (i18nLabelKey) {
          const translated = $t(i18nLabelKey as string, { unit });
          if (translated) {
            labelText = translated;
          }
        }

        baseCols.push({
          name: f.id,
          label: labelText,
          field: f.id,
          sortable,
          hint: f.hint,
          min: f.min,
          max: f.max,
          step: f.step,
          align,
          inputComponent,
          editableInline,
          options,
          optionsId: f.optionsId,
          optionLabelKey: f.optionLabelKey,
          tooltip,
          type: f.type,
          columnSize: f.columnSize,
          minColumnWidth: f.minColumnWidth,
          maxColumnWidth: f.maxColumnWidth,
          readOnlyWhen: f.readOnlyWhen,
          readOnlyDisplayField: f.readOnlyDisplayField,
          optionLabelsAreKeys: f.optionLabelsAreKeys,
          optionLabelPrefix: f.optionLabelPrefix,
          optionOrder: f.optionOrder,
        });
      }
    });

  // Planner prefilled tables gain a reference-year kgCO₂eq column (before the
  // current kgCO₂eq) and a "% of reference year" slider (after it). Snapshot
  // rows carry the values; other rows render blank/no slider.
  if (props.showReferenceColumns) {
    const kgIdx = baseCols.findIndex((c) => c.name === 'kg_co2eq');
    const referenceCol: TableViewColumn = {
      name: 'reference_kg_co2eq',
      label: $t('planner_reference_kg_col'),
      field: 'reference_kg_co2eq',
      sortable: false,
      align: 'right',
      inputComponent: QInput,
      editableInline: false,
      type: 'number',
    };
    const sliderCol: TableViewColumn = {
      name: 'percentage_of_reference_year',
      label: $t('planner_percentage_col'),
      field: 'percentage_of_reference_year',
      sortable: false,
      align: 'left',
      inputComponent: QInput,
      editableInline: false,
      type: 'number',
      // Grant tables carry an extra kg column, so the slider cedes a little
      // room to keep the table inside the viewport.
      minColumnWidth: props.projectYearsCount != null ? 150 : 180,
    };
    if (kgIdx >= 0) {
      baseCols.splice(kgIdx, 0, referenceCol);
      baseCols.splice(kgIdx + 2, 0, sliderCol);
    } else {
      baseCols.push(referenceCol, sliderCol);
    }
  }

  // Project Grant tables: the kgCO₂eq column reads per-year and a "× project
  // years" column follows it, so a value and its project total sit side by
  // side (#1979). Same kg_co2eq field — the multiply is presentation only.
  if (props.projectYearsCount != null) {
    const kgIdx = baseCols.findIndex((c) => c.name === 'kg_co2eq');
    if (kgIdx >= 0) {
      baseCols[kgIdx] = {
        ...baseCols[kgIdx],
        label: $t('planner_kg_per_year_col'),
        minColumnWidth: undefined,
        columnSize: 'xs',
      };
      baseCols.splice(kgIdx + 1, 0, {
        name: 'project_kg_co2eq',
        label: $t('planner_kg_project_col', {
          years: props.projectYearsCount,
        }),
        field: 'kg_co2eq',
        sortable: true,
        align: 'right',
        inputComponent: QInput,
        editableInline: false,
        type: 'number',
        columnSize: 'xs',
      });
    }
  }

  if (showTableActions.value) {
    baseCols.push({
      name: 'action',
      label: $t('common_actions'),
      field: 'action',
      align: 'right',
      sortable: false,
      inputComponent: QInput,
      hint: undefined,
      min: undefined,
      max: undefined,
      step: undefined,
      editableInline: false,
      options: undefined,
      tooltip: undefined,
      type: 'text',
      columnSize: 'sm',
      minColumnWidth: undefined,
      maxColumnWidth: undefined,
    });
  }
  return baseCols;
});

const taxonomyKindLabelMap = computed<Record<string, string>>(() => {
  const taxo = moduleStore.state.taxonomySubmodule[props.submoduleType];
  const map: Record<string, string> = {};
  taxo?.children?.forEach((node) => {
    if (node.name && node.label) {
      if (node.translation_key && $te(node.translation_key)) {
        map[node.name] = $t(node.translation_key);
      } else if ($te(node.name)) {
        map[node.name] = $t(node.name);
      } else {
        map[node.name] = node.label;
      }
    }
  });
  return map;
});

const inlineOptionsMap = computed<
  Record<string, Array<{ value: string; label: string }>>
>(() => {
  const map: Record<string, Array<{ value: string; label: string }>> = {};
  qCols.value.forEach((col) => {
    map[col.name] = (col.options ?? []).map((option) => ({
      ...option,
      label: $te(option.label) ? $t(option.label) : option.label,
    }));
  });
  return map;
});

function getInlineOptions(
  col: TableViewColumn,
): Array<{ value: string; label: string }> {
  const inlineOptions = inlineOptionsMap.value[col.name] ?? [];
  const result = inlineOptions.map((option) => ({
    ...option,
    label: $t(option.label),
  }));
  return result;
}

function isRowConditionallyReadOnly(
  row: Record<string, unknown>,
  col: TableViewColumn,
): boolean {
  if (!col.readOnlyWhen) return false;
  const val = row[col.readOnlyWhen.fieldId];
  const hasValue = val !== null && val !== undefined && val !== '';
  return col.readOnlyWhen.hasValue ? hasValue : !hasValue;
}

function renderCell(
  row: ModuleRow,
  col: {
    field: string;
    name: string;
    maxColumnWidth?: number;
    options?: Array<{ value: string; label: string }>;
    optionLabelPrefix?: string;
    optionLabelKey?: string;
    optionsId?: string;
  },
) {
  if (col.field === 'origin_name') {
    const name = row['origin_name'] as string | undefined;
    const iata = row['origin_iata'] as string | undefined;
    return iata ? `${name ?? iata} (${iata})` : (name ?? '-');
  }
  if (col.field === 'destination_name') {
    const name = row['destination_name'] as string | undefined;
    const iata = row['destination_iata'] as string | undefined;
    return iata ? `${name ?? iata} (${iata})` : (name ?? '-');
  }
  if (col.field === 'traveler_name') {
    const user_institutional_id = row['user_institutional_id'] as
      string | null | undefined;
    return resolveTravelerCellText(
      user_institutional_id,
      headcountMembersMap.value,
      authStore.user?.institutional_id,
      authStore.displayName,
      $t,
    );
  }
  const val = row[col.field];
  if (val === undefined || val === null || val === '') return '-';
  if (col.name === 'project_kg_co2eq') {
    return nOrDash((val as number) * (props.projectYearsCount ?? 1), {
      options: {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      },
    });
  }
  if (
    col.name === 'kg_co2eq' ||
    col.name === 't_co2eq' ||
    col.name === 'reference_kg_co2eq'
  ) {
    return nOrDash(val as number, {
      options: {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      },
    });
  }
  // If column has options, look up the translated label for the value
  if (col.options && typeof val === 'string') {
    const translated = inlineOptionsMap.value[col.name];
    const option = (translated ?? col.options).find((opt) => opt.value === val);
    if (option) {
      return option.label;
    }
  }
  // Factor-sourced options: translate using optionLabelPrefix
  if (col.optionLabelPrefix && typeof val === 'string') {
    return $t(val.toLowerCase(), val);
  }
  // Translate stored values that are i18n keys (e.g. researchfacility_type: fish, rodent)
  if (col.optionLabelKey && typeof val === 'string') {
    const key = col.optionLabelKey.replace('{value}', val.toLowerCase());
    return $te(key) ? $t(key) : val;
  }
  // Factor-sourced kind/subkind: look up label from taxonomy
  if (col.optionsId === 'kind' && typeof val === 'string') {
    return taxonomyKindLabelMap.value[val] ?? val;
  }
  if (typeof val === 'string') return val;
  if (typeof val === 'number') {
    return nOrDash(val, { options: props.moduleConfig?.numberFormatOptions });
  }
  console.warn('Unexpected cell value type', val);
  return String(val);
}

// The read-only fallback for a normally-editableInline cell (locked by
// readOnlyWhen or #951 policy) used to read the raw stored value directly —
// correct for plain text/numbers, but silently un-translated for
// option-label fields (e.g. headcount sius_code stores "57", not "Personnel
// administratif"). Reuses renderCell so every rendering path shares one
// formatting/translation source of truth.
function renderReadOnlyInlineCell(row: ModuleRow, col: TableViewColumn) {
  const targetCol = col.readOnlyDisplayField
    ? { ...col, field: col.readOnlyDisplayField }
    : col;
  return renderCell(row, targetCol);
}

function getItemName(row: ModuleRow): string {
  return String(row?.name ?? $t('common_this_item'));
}

function getRowId(row: ModuleRow): number | null {
  const n = Number(row.id);
  return Number.isFinite(n) ? n : null;
}

// Uncommitted percentage per row: what the slider shows mid-drag and what the
// typed field shows mid-edit. Both controls read it, so the number tracks the
// slider handle live instead of jumping only once the drag ends.
const percentageDrafts = ref<Record<string, number>>({});

function percentageStored(row: ModuleRow): number {
  return (row.percentage_of_reference_year as number) ?? 100;
}

function percentageOf(row: ModuleRow): number {
  const id = String(getRowId(row));
  return percentageDrafts.value[id] ?? percentageStored(row);
}

// The field hugs its digits so the trailing "%" always sits one space after the
// last one, rather than at the far side of a box sized for three digits. The
// surrounding block keeps a fixed width, so the slider does not resize with it.
function percentageFieldWidth(row: ModuleRow): Record<string, string> {
  return { width: `${String(percentageOf(row)).length}ch` };
}

// Remount key for the typed field. Clearing the field leaves the model
// untouched, so Vue has nothing to re-render against and the box would stay
// blank over a row that still has a value; bumping the key on commit rebuilds
// it from the row.
const percentageInputRevisions = ref<Record<string, number>>({});

function percentageInputKey(row: ModuleRow): string {
  const id = String(getRowId(row));
  return `${id}-${percentageInputRevisions.value[id] ?? 0}`;
}

// Dragging: move the number with the handle. No PATCH until the drag ends,
// which QSlider signals with @change.
function onPercentageDrag(row: ModuleRow, value: number | null) {
  if (value === null) return;
  percentageDrafts.value[String(getRowId(row))] = value;
}

// Typing: drive the slider live, capped, so the two never disagree. An empty
// or unparseable box holds the last value rather than guessing one.
function onPercentageTyped(row: ModuleRow, raw: string | number | null) {
  const value = clampReferencePercentage(raw);
  if (value === null) return;
  percentageDrafts.value[String(getRowId(row))] = value;
}

// Blur/Enter commits the typed value; the draft is dropped either way so the
// row's stored percentage takes back over.
async function commitPercentage(row: ModuleRow) {
  const id = getRowId(row);
  if (id == null) return;
  const key = String(id);
  const draft = percentageDrafts.value[key];
  if (draft !== undefined && draft !== percentageStored(row)) {
    await onPercentageChange(row, draft);
  }
  delete percentageDrafts.value[key];
  percentageInputRevisions.value[key] =
    (percentageInputRevisions.value[key] ?? 0) + 1;
}

// Planner slider: PATCH the snapshot row's percentage; the backend recomputes
// kg_co2eq = reference × %, and patchItem refetches so the kg cell updates.
async function onPercentageChange(row: ModuleRow, value: number) {
  const id = getRowId(row);
  if (id == null) return;
  try {
    await moduleStore.patchItem(
      props.moduleType as Module,
      props.submoduleType,
      props.unitId,
      String(props.year),
      id,
      { percentage_of_reference_year: value },
      props.carbonReportId,
    );
  } catch {
    $q.notify({
      color: 'negative',
      message: $t('common_save_error'),
      position: 'top',
    });
  } finally {
    // The refetched row is authoritative from here; a surviving draft would
    // shadow it, and on a failed PATCH it would show a value never stored.
    delete percentageDrafts.value[String(id)];
  }
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

function validateUsageHoursWeek(value: number) {
  if (!Number.isFinite(value))
    return {
      valid: false,
      parsed: null,
      error: $t('validation_number_required'),
    };
  if (value < 0)
    return {
      valid: false,
      parsed: null,
      error: $t('validation_must_be_non_negative'),
    };
  if (value > 168)
    return {
      valid: false,
      parsed: null,
      error: $t('validation_max_hours_per_week'),
    };
  return { valid: true, parsed: value, error: null };
}

function validateNumberOfTrips(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return { valid: false, parsed: null, error: $t('validation_required') };
  }
  const n = Number(value);
  if (!Number.isFinite(n))
    return {
      valid: false,
      parsed: null,
      error: $t('validation_number_required'),
    };
  if (n < 1)
    return {
      valid: false,
      parsed: null,
      error: $t('validation_must_be_at_least_one'),
    };
  return { valid: true, parsed: Math.floor(n), error: null };
}

async function commitInline(
  row: ModuleRow,
  col: {
    name: string;
    field: string;
    editableInline?: boolean;
    type?: string;
    min?: number;
    max?: number;
  },
) {
  if (!col.editableInline) return;
  const isUsageField =
    col.name === 'active_usage_hours_per_week' ||
    col.name === 'standby_usage_hours_per_week';
  const isNumberOfTrips = col.name === 'number_of_trips';
  const isNumeric = col.type === 'number' || isUsageField || isNumberOfTrips;
  const rawVal = row[col.field];

  const valueToSave = (() => {
    // Clear any previous error before validating
    setError(row, col, null);
    if (isUsageField) {
      const activeVal = Number(row['active_usage_hours_per_week']) || 0;
      const standbyVal = Number(row['standby_usage_hours_per_week']) || 0;
      const validation = validateUsageHoursWeek(activeVal + standbyVal);
      if (!validation.valid) {
        setError(row, col, validation.error);
        return null;
      }
      // parse raw value to number to ensure consistent type (could be string from input)
      const parsedVal = Number(rawVal);
      return Number.isFinite(parsedVal) ? parsedVal : rawVal;
    }
    if (isNumberOfTrips) {
      const validation = validateNumberOfTrips(rawVal);
      if (!validation.valid) {
        setError(row, col, validation.error);
        return null;
      }
      return validation.parsed;
    }
    if (isNumeric) {
      const s = typeof rawVal === 'string' ? rawVal.trim() : String(rawVal);
      if (s.includes(',')) {
        // Targeted message: FR/CH users instinctively type a comma separator
        setError(row, col, $t('validation_use_dot_not_comma'));
        return null;
      }
      // Canonical dot-decimal only: optional minus, digits, optional single dot + digits
      if (!/^-?\d+(\.\d+)?$/.test(s)) {
        setError(row, col, $t('validation_number_format'));
        return null;
      }
      const n = Number(s);
      // Validate min/max constraints
      if (col.min !== undefined && n < col.min) {
        setError(row, col, $t('validation_must_be_at_least', { min: col.min }));
        return null;
      }
      if (col.max !== undefined && n > col.max) {
        setError(row, col, $t('validation_must_be_at_most', { max: col.max }));
        return null;
      }
      return n;
    }
    return rawVal;
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
      props.carbonReportId,
    );
  } catch (err) {
    let msg = err instanceof Error ? err.message : $t('validation_save_failed');
    if (msg === 'DUPLICATE_INSTITUTIONAL_ID') {
      msg = $t('headcount-member-error-duplicate-uid', {
        label:
          typeof INSTITUTIONAL_ID_LABEL !== 'undefined'
            ? INSTITUTIONAL_ID_LABEL
            : '',
      });
    }
    setError(row, col, msg);
  }
}

function rowClasses(row: ModuleRow) {
  return {
    'row-new': isNewIncomplete(row),
    'row-incomplete': !isComplete(row),
  };
}

function cellClasses(row: ModuleRow, col: { name: string; field: string }) {
  if (col.name === 'kg_co2eq') {
    const thresholdVal = Number(props.threshold?.value);
    const rawVal = row?.[col.field];
    const val = typeof rawVal === 'number' ? rawVal : Number(rawVal);

    if (
      Number.isFinite(thresholdVal) &&
      Number.isFinite(val) &&
      val > thresholdVal
    ) {
      return 'text-negative';
    }
  }
  return '';
}

function getColumnStyle(col: TableViewColumn) {
  const style: Record<string, string> = {};
  const minWidth =
    col.minColumnWidth ??
    (col.columnSize !== undefined ? COLUMN_SIZES[col.columnSize] : undefined);
  if (minWidth !== undefined) {
    style['--min-column-width'] = `${minWidth}px`;
  }
  if (col.maxColumnWidth !== undefined) {
    style['--max-column-width'] = `${col.maxColumnWidth}px`;
  }
  return style;
}

function getColumnClasses(row: ModuleRow, col: TableViewColumn) {
  const hasMinWidth =
    col.minColumnWidth !== undefined || col.columnSize !== undefined;
  return [
    cellClasses(row, col),
    'table-cell',
    { 'column-max-width': col.maxColumnWidth !== undefined },
    { 'column-min-width': hasMinWidth },
  ];
}

function isNew(row: ModuleRow) {
  return Boolean(row.is_new);
}

// Usage fields a new equipment (#259) must fill before the module can validate.
const EQUIPMENT_REQUIRED_USAGE_FIELDS = [
  'active_usage_hours_per_week',
  'standby_usage_hours_per_week',
];

// Highlight (orange contour + em-dash placeholder) an empty active/standby
// usage cell of a new equipment row, so the user knows it needs filling.
function isRequiredEmptyUsageCell(
  row: ModuleRow,
  col: { field: string },
): boolean {
  return (
    props.moduleType === MODULES.Equipment &&
    isNew(row) &&
    EQUIPMENT_REQUIRED_USAGE_FIELDS.includes(col.field) &&
    !hasValue(row[col.field])
  );
}

// A new equipment only needs the "new" emphasis (badge, row highlight, float to
// top) until its usage is entered; once active + standby are filled it behaves
// like a normal row (#259).
function isNewIncomplete(row: ModuleRow): boolean {
  return (
    isNew(row) &&
    EQUIPMENT_REQUIRED_USAGE_FIELDS.some((field) => !hasValue(row[field]))
  );
}

function hasValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim() !== '';
  return true;
}

function hasRequiredValues(row: ModuleRow, fields: string[]) {
  return fields.every((fieldId) => hasValue(row[fieldId]));
}

function isCompleteEquipement(row: ModuleRow) {
  const required = [
    'name',
    'equipment_class',
    'active_usage_hours_per_week',
    'standby_usage_hours_per_week',
    'active_power_w',
    'standby_power_w',
  ];

  return hasRequiredValues(row, required);
}

function isCompleteResearchFacilities(row: ModuleRow) {
  const required = ['researchfacility_name', 'use', 'use_unit'];

  return hasRequiredValues(row, required);
}

function isCompleteHeadcount(row: ModuleRow) {
  const requiredMember = ['name', 'fte', 'function'];
  const requiredStudent = ['fte'];
  // implicit behavior: if sciper is set, it's a member
  // todo: sciper field should not exist: maybe user_id to be agnostic
  if (hasValue(row.sciper)) {
    return hasRequiredValues(row, requiredMember);
  }

  return hasRequiredValues(row, requiredStudent);
}

//  dependence on the submodule type
function isCompleteExternalCloud(row: ModuleRow) {
  const required = ['service_type', 'provider', 'spent_amount'];
  return hasRequiredValues(row, required);
}

function isCompleteExternalAI(row: ModuleRow) {
  const required = [
    'provider',
    'usage_type',
    'requests_per_user_per_day',
    'fte_count',
  ];
  return hasRequiredValues(row, required);
}

function isCompletePurchase(row: ModuleRow) {
  const required = [
    'name',
    'quantity',
    'purchase_institutional_code',
    'total_spent_amount',
  ];
  return required.every(
    (k) => row[k] !== null && row[k] !== undefined && row[k] !== '',
  );
}

function isCompletePurchaseAdditional(row: ModuleRow) {
  const required = ['name', 'unit', 'annual_consumption', 'coef_to_kg'];
  return required.every(
    (k) => row[k] !== null && row[k] !== undefined && row[k] !== '',
  );
}

function isComplete(row: ModuleRow) {
  const requiredFieldIds = props.submoduleConfig?.requiredFieldIds ?? [];
  if (requiredFieldIds.length > 0) {
    return hasRequiredValues(row, requiredFieldIds);
  }

  if (props.moduleType === MODULES.Headcount) {
    // For Headcount, consider complete if name and status are set
    return isCompleteHeadcount(row);
  }
  if (props.moduleType === MODULES.Equipment) {
    return isCompleteEquipement(row);
  }
  if (props.moduleType === MODULES.ResearchFacilities) {
    return isCompleteResearchFacilities(row);
  }
  if (
    props.moduleType === MODULES.ExternalCloudAndAI &&
    props.submoduleType === SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds
  ) {
    return isCompleteExternalCloud(row);
  }
  if (
    props.moduleType === MODULES.ExternalCloudAndAI &&
    props.submoduleType === SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai
  ) {
    return isCompleteExternalAI(row);
  }
  if (props.moduleType === MODULES.Purchase) {
    if (props.submoduleType === SUBMODULE_PURCHASE_TYPES.PurchasesCentralized) {
      return isCompletePurchaseAdditional(row);
    }
    return isCompletePurchase(row);
  }
  if (props.moduleType === MODULES.ProfessionalTravel) {
    const required = ['origin', 'destination', 'user_institutional_id'];
    return required.every(
      (k) => row[k] !== null && row[k] !== undefined && row[k] !== '',
    );
  }
  if (props.moduleType === MODULES.ProcessEmissions) {
    const baseRequired = ['category', 'quantity'];
    const hasBaseRequired = hasRequiredValues(row, baseRequired);
    if (!hasBaseRequired) {
      return false;
    }

    if (row.category === 'Refrigerants') {
      return (
        row.subcategory !== null &&
        row.subcategory !== undefined &&
        row.subcategory !== ''
      );
    }
    return true;
  }
  if (props.moduleType === MODULES.Buildings) {
    if (props.submoduleType === SUBMODULE_BUILDINGS_TYPES.EnergyCombustion) {
      const required = ['name', 'quantity'];
      return required.every(
        (k) => row[k] !== null && row[k] !== undefined && row[k] !== '',
      );
    }
    const required = [
      'building_name',
      'room_name',
      'room_type',
      'room_surface_square_meter',
    ];
    return required.every(
      (k) => row[k] !== null && row[k] !== undefined && row[k] !== '',
    );
  }
  throw new Error(`Unknown module type: ${props.moduleType}`);
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
    // Module-specific payload adjustments
    if (moduleType === MODULES.Equipment) {
      // Backend will auto-resolve power_factor_id and power values
      // based on class/sub_class, so no need to fetch them here
      basePayload.active_usage_hours_per_week = Number(
        payload.active_usage_hours_per_week,
      );
      basePayload.standby_usage_hours_per_week = Number(
        payload.standby_usage_hours_per_week,
      );
    }

    const p = isEdit
      ? store.patchItem(
          moduleType,
          props.submoduleType,
          unit,
          year,
          equipmentId,
          basePayload,
          props.carbonReportId,
        )
      : store.postItem(
          moduleType,
          unit,
          year,
          props.submoduleType,
          basePayload,
          undefined,
          props.carbonReportId,
        );

    await p.finally(() => {
      editDialogOpen.value = false;
      editRowData.value = null;
    });
  };

  perform();
}

function onUploadCsv() {
  showUploadDialog.value = true;
}

function onDownloadTemplate() {
  const fileName = getTemplateFileName(
    props.moduleType as Module,
    props.submoduleType,
  );
  if (!fileName) return;

  const a = document.createElement('a');
  a.href = `/templates/${fileName}`;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  $q.notify({
    color: 'info',
    message: $t('common_download_csv_template_mock') || 'CSV template download',
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
    .deleteItem(
      moduleType,
      submoduleType,
      unit,
      year,
      deleteRowId.value,
      props.carbonReportId,
    )
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
      carbonReportId: props.carbonReportId,
    });
  } else {
    // Only change page if sort didn't change
    await moduleStore.getSubmoduleData({
      submoduleType: props.submoduleType,
      moduleType: props.moduleType,
      unit: props.unitId,
      year: String(props.year),
      carbonReportId: props.carbonReportId,
    });
  }
}

watch(
  () => moduleStore.state.expandedSubmodules[props.submoduleType],
  (isExpanded, oldValue) => {
    // Fetch data when expanded (either from undefined/false to true, or already true)
    if (isExpanded) {
      // Only fetch if we haven't loaded yet OR if we just expanded from collapsed
      const shouldFetch =
        !moduleStore.state.loadedSubmodules[props.submoduleType] ||
        oldValue === false;

      if (shouldFetch) {
        moduleStore.initializeSubmoduleState(props.submoduleType);

        // table-specific work
        moduleStore.getSubmoduleData({
          submoduleType: props.submoduleType,
          moduleType: props.moduleType,
          unit: props.unitId,
          year: String(props.year),
          carbonReportId: props.carbonReportId,
        });
        moduleStore.getSubmoduleTaxonomy(
          props.moduleType,
          props.submoduleType,
          String(props.year),
        );
      }
    }
  },
  { immediate: true },
);

watch(
  () => moduleStore.state.dataSubmodule[props.submoduleType],
  () => {},
  { deep: true, immediate: true },
);

onMounted(async () => {
  moduleStore.initializeSubmoduleState(props.submoduleType);

  // Check if already expanded on mount and fetch data if so
  if (moduleStore.state.expandedSubmodules[props.submoduleType]) {
    moduleStore.getSubmoduleData({
      submoduleType: props.submoduleType,
      moduleType: props.moduleType,
      unit: props.unitId,
      year: String(props.year),
      carbonReportId: props.carbonReportId,
    });
    moduleStore.getSubmoduleTaxonomy(
      props.moduleType,
      props.submoduleType,
      String(props.year),
    );
  }

  // For professional travel, pre-load headcount members to resolve traveler names
  // in the table. Plan reports hold no member roster, so planner tables
  // (carbonReportId set) read the reference year's Calculator roster instead —
  // copied reference rows carry real institutional ids (#2018). Units without a
  // Calculator report for that year fail the lookup and keep the fallback labels.
  if (
    props.moduleType === MODULES.ProfessionalTravel &&
    props.unitId &&
    props.year
  ) {
    try {
      const rosterReportId =
        props.carbonReportId != null
          ? await moduleStore.resolveCarbonReportId(
              props.unitId,
              props.factorYear ?? props.year,
              CARBON_PROJECT.calculator,
            )
          : await moduleStore.resolveCarbonReportId(props.unitId, props.year);
      const members: HeadcountMemberDropdownItem[] =
        await getHeadcountMembers(rosterReportId);
      headcountMembersMap.value = new Map(
        members.map((m) => [m.institutional_id, m.name]),
      );
    } catch (err) {
      console.error(
        'Failed to load headcount members for professional travel',
        err,
      );
    }

    // Clear inline errors on mount
    inlineErrors.value = {};

    // SSE subscription is job-scoped and triggered on sync initiation
  }
});

// Unsubscribe from SSE when component unmounts
onUnmounted(() => {
  dataManagementStore.unsubscribeFromJobUpdates();
});
</script>

<style scoped lang="scss">
.table-cell {
  white-space: normal;
  word-wrap: break-word;
}

.column-min-width {
  min-width: var(--min-column-width, 100%);
  white-space: normal;
}

.column-max-width {
  max-width: var(--max-column-width, 100%);
  white-space: normal;
}

.table-search {
  min-width: 240px;
}

/* New / incomplete equipment rows (#259) are tinted with the banner colour.
   The :deep + .q-tr selector must out-specify the striped-row rule below,
   which otherwise repaints every even row. */
.co2-table :deep(tbody tr.q-tr.row-new),
.co2-table :deep(tbody tr.q-tr.row-incomplete) {
  background: #fff4e5;
}

.co2-table :deep(tbody tr.q-tr.row-new) {
  border-left: 4px solid #ffa503;
}

/* NEW badge next to a new equipment's name (#259). Outline badge follows
   currentColor for both text and border. */
.badge-new {
  color: #ffa503;
}

/* Banner reminding the user to fill new equipment usage (#259): no border,
   orange info icon. */
.equipment-new-banner {
  background: #fff4e5;
}

.equipment-new-banner__icon {
  color: #ffa503;
}

/* Empty required usage cell on a new equipment row (#259): orange contour so
   the user immediately sees what must be filled before validating. */
.inline-input--required-empty :deep(.q-field__control) {
  border: 1px solid #ffa503;
  border-radius: 4px;
}

.inline-input--required-empty :deep(.q-field__control):hover {
  border-color: #e09400;
}

.cell-content {
  display: inline-flex;
  align-items: center;
}

.reference-slider {
  min-width: 160px;

  // Clears the slider's thumb, which overhangs the end of its track.
  gap: 1rem;
}

.reference-slider__value {
  display: flex;
  align-items: center;

  // Fixed here rather than on the field, so the slider keeps its width while
  // the field inside grows with its digits.
  width: 3.25rem;

  // Digits of equal width, so the "%" does not shift as the value changes.
  font-variant-numeric: tabular-nums;
}

.reference-slider__field {
  // It is a table value that happens to be editable, so it takes the cell's
  // type. `font` (not `font-size`) because the q-field root itself carries
  // Quasar's $input-font-size — inheriting only in the children would inherit
  // that, not the cell's.
  font: inherit;

  :deep(.q-field__control),
  :deep(.q-field__native) {
    font: inherit;
    color: inherit;
    min-height: 0;
    padding: 0;
  }

  :deep(input) {
    text-align: left;

    // Spinners would halve the usable width of a 3-digit field.
    &::-webkit-outer-spin-button,
    &::-webkit-inner-spin-button {
      appearance: none;
      margin: 0;
    }
  }

  :deep(input[type='number']) {
    appearance: textfield;
  }
}

// Trailing unit: it labels the field, it is not part of it. The field carries
// the accessible name, so this is decorative and inert.
.reference-slider__unit {
  // One space after the last digit — no more.
  padding-left: 0.25em;
  user-select: none;
  pointer-events: none;
}

.tooltip {
  max-width: 280px;
  white-space: normal;
}

.co2-table .q-table td {
  width: 100px;
}

.co2-table :deep(tbody tr:nth-child(even)) {
  background-color: var(--row-alt-color, transparent);
}
</style>

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

  /* Grant tables carry two extra kg columns; letting the headers wrap keeps
     every column at its content width instead of its longest header line. */
  &--wrap-headers th {
    white-space: normal;
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

  th,
  td {
    padding: tokens.$spacing-xs tokens.$spacing-md;
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

  td
    .q-field--outlined:not(.q-field--focused):not(.q-field--error)
    .q-field__control::before {
    border-color: transparent;
  }

  td
    .q-field--outlined:not(.q-field--focused):not(.q-field--error):not(
      .q-field--disabled
    ):hover
    .q-field__control {
    background: tokens.$table-field-hover-bg;
  }

  td .inline-input,
  td .inline-select-wrapper .q-select {
    display: inline-flex;
    width: auto;
    max-width: 100%;
    vertical-align: middle;
  }

  td .inline-input .q-field__native,
  td .inline-input .q-field__input,
  td .inline-select-wrapper .q-field__native,
  td .inline-select-wrapper .q-field__input {
    field-sizing: content;
    min-width: 1ch;
    font-size: tokens.$text-size-sm;
  }

  td .inline-input .q-field__append,
  td .inline-select-wrapper .q-field__append {
    padding-left: tokens.$spacing-xs;
  }

  td .inline-input--required-empty {
    width: 100%;
  }

  td .inline-input--required-empty .q-field__native,
  td .inline-input--required-empty .q-field__input {
    field-sizing: auto;
    width: 100%;
  }

  .inline-edit-icon {
    color: tokens.$table-inline-icon-color;
  }

  .q-field--focused .inline-edit-icon,
  .q-field--disabled .inline-edit-icon {
    display: none;
  }

  td .q-select__dropdown-icon {
    font-size: 18px;
    color: tokens.$table-inline-icon-color;
  }

  td .q-select:not(.q-field--disabled),
  td .q-select:not(.q-field--disabled) * {
    cursor: pointer;
  }

  .action-btn {
    width: tokens.$table-action-size;
    height: tokens.$table-action-size;
    min-height: 0;
    padding: 0;
    border-radius: tokens.$radius-default;
  }

  .action-btn .q-icon {
    font-size: tokens.$table-action-icon-size;
  }

  .action-btn + .action-btn {
    margin-left: tokens.$spacing-xs;
  }

  .action-btn:not(.disabled):hover {
    background: tokens.$table-action-hover-bg;
  }

  .action-btn--delete:not(.disabled):hover {
    background: tokens.$table-action-delete-hover-bg;
  }

  .action-btn--delete:not(.disabled):hover .q-icon {
    color: tokens.$icon-color-white;
  }
}

/* Teleported to <body>, so it must be styled outside .co2-table and unscoped. */
.q-tooltip.action-tooltip {
  padding: tokens.$spacing-lg tokens.$spacing-xl;
  font-size: tokens.$text-size-sm;
  line-height: normal;
}
</style>
