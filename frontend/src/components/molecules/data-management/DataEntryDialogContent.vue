<script setup lang="ts">
import { useDataEntryDialog } from '@/composables/useDataEntryDialog';
import type {
  SyncJobResponse,
  ImportRow,
} from '@/stores/backofficeDataManagement';
import { TargetType } from '@/stores/backofficeDataManagement';
import { computed, watch, toRef } from 'vue';

interface Props {
  modelValue: boolean;
  row: ImportRow;
  year: number;
  targetType: TargetType;
}

const props = withDefaults(defineProps<Props>(), {});
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'completed', job: SyncJobResponse): void;
  (e: 'progressing', job: SyncJobResponse): void;
}>();

const {
  showDialog,
  selectedFiles,
  isUploading,
  isConnecting,
  connectorsList,
  selectedConnector,
  apiConnectorLuid,
  connectionConfigured,
  allApiFieldsFilled,
  showOverwriteWarning,
  showOverwriteWarningAPI,
  handleEnterKey,
  resetDialog,
  loadConnectorOptions,
  uploadFiles,
  connectAndSync,
} = useDataEntryDialog({
  row: toRef(props, 'row'),
  year: toRef(props, 'year'),
  targetType: toRef(props, 'targetType'),
  onComplete: (job: SyncJobResponse) => emit('completed', job),
  onProgressing: (job: SyncJobResponse) => emit('progressing', job),
});

const connectorOptions = computed(() =>
  connectorsList.value.map((c) => ({ label: c.label, value: c.connector })),
);

watch(
  () => props.modelValue,
  (newVal) => {
    showDialog.value = newVal;
    if (newVal) {
      resetDialog();
      loadConnectorOptions();
    }
  },
);

watch(showDialog, (newVal) => {
  emit('update:modelValue', newVal);
});
</script>

<template>
  <q-dialog
    v-model="showDialog"
    class="modal modal--lg"
    persistent
    @keyup.escape="showDialog = false"
    @keyup.enter="handleEnterKey"
  >
    <q-card class="column no-wrap" style="width: 800px; max-width: 80vw">
      <q-card-section class="flex justify-between items-center flex-shrink">
        <div class="text-h4 text-weight-medium">
          <!--
            Reduction objectives share a single TargetType (REDUCTION_OBJECTIVES)
            for all three CSV types (footprint, population, scenarios), so
            $t(TargetType[targetType]) would always show "REDUCTION_OBJECTIVES".
            Instead we use the card's labelKey as the title noun directly,
            e.g. "Import Institution's Carbon Footprint Data".
          -->
          <template
            v-if="
              props.row.reductionObjectiveTypeId !== undefined &&
              props.row.labelKey
            "
          >
            {{
              $t('data_management_import_title', {
                type: $t(props.row.labelKey).toLocaleLowerCase(),
              })
            }}
          </template>
          <template v-else>
            {{
              $t('data_management_import_title', {
                type: $t(TargetType[props.targetType]),
              })
            }}
            <span
              v-if="
                props.row.dataEntryTypeId == undefined && props.row.moduleTypeId
              "
            >
              {{ props.row.moduleTypeId ? `- ${$t(props.row.labelKey)}` : '' }}
            </span>
            {{ props.row.dataEntryTypeId ? `- ${$t(props.row.labelKey)}` : '' }}
          </template>
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

      <q-card-section class="q-gutter-md">
        <div class="text-subtitle1 text-weight-medium">
          {{ $t('data_management_tab_upload_csv') }}
        </div>
        <q-banner
          v-if="showOverwriteWarning"
          color="warning"
          class="q-mb-sm"
          inline-action
        >
          <q-icon name="warning" size="sm" class="q-mr-sm" />
          {{ $t('data_management_last_upload_overwrite') }}
        </q-banner>
        <div data-testid="data-entry-file-input">
          <q-file
            v-model="selectedFiles"
            dense
            outlined
            multiple
            :hint="$t('data_management_supported_file_types')"
            counter
            accept=".csv, text/csv"
          />
        </div>

        <template v-if="row.hasApi && targetType === TargetType.DATA_ENTRIES">
          <div class="row items-center q-my-sm">
            <q-separator class="col" />
            <span class="q-px-md text-grey-6 text-caption">{{
              $t('common_or')
            }}</span>
            <q-separator class="col" />
          </div>

          <div>
            <div class="text-subtitle1 text-weight-medium q-mb-sm">
              {{ $t('data_management_tab_connect_api') }}
            </div>
            <q-banner
              v-if="showOverwriteWarningAPI"
              color="warning"
              class="q-mb-sm"
              inline-action
            >
              <q-icon name="warning" size="sm" class="q-mr-sm" />
              {{ $t('data_management_last_upload_overwrite') }}
            </q-banner>
            <div class="q-gutter-sm q-mt-sm">
              <q-select
                v-model="selectedConnector"
                :options="connectorOptions"
                emit-value
                map-options
                dense
                outlined
                :label="$t('data_management_api_connector')"
              />
              <q-banner
                v-if="selectedConnector && !connectionConfigured"
                dense
                class="bg-grey-3"
              >
                {{ $t('data_management_connection_not_configured_hint') }}
              </q-banner>
              <q-input
                v-model="apiConnectorLuid"
                dense
                outlined
                :placeholder="$t('data_management_api_luid')"
              />
            </div>
          </div>
        </template>

        <div class="text-caption text-grey-7 q-mt-sm">
          {{ $t('data_management_overwrite_warning') }}
        </div>
      </q-card-section>

      <q-separator />

      <q-card-actions class="q-px-md q-pb-md">
        <q-btn
          aria-label="data-entry-save"
          :label="
            selectedFiles && selectedFiles.length > 0
              ? $t('data_management_upload')
              : allApiFieldsFilled
                ? $t('data_management_api_connect_and_sync')
                : $t('common_save')
          "
          color="accent"
          unelevated
          class="q-px-xl text-weight-medium"
          :loading="isUploading || isConnecting"
          :disable="isUploading || isConnecting"
          @click="
            selectedFiles && selectedFiles.length > 0
              ? uploadFiles()
              : allApiFieldsFilled
                ? connectAndSync()
                : (showDialog = false)
          "
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<style scoped></style>
