<script setup lang="ts">
import { useModuleConfig } from 'src/composables/useModuleConfig';
import { useRecalculation } from 'src/composables/useRecalculation';
import {
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import UploadCardData from 'src/components/molecules/data-management/UploadCardData.vue';
import UploadCardFactors from 'src/components/molecules/data-management/UploadCardFactors.vue';
import type { SubmoduleConfig as SubmoduleConfigItem } from 'src/constant/backoffice-module-config';

interface Props {
  module: string;
  selectedYear: number;
  isModuleEnabled: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'dataUpload', row: ImportRow, targetType: TargetType): void;
  (e: 'factorUpload', row: ImportRow, targetType: TargetType): void;
  (e: 'download', row: ImportRow, targetType: TargetType): void;
  (e: 'recalculate', sub: SubmoduleConfigItem): void;
}>();

const { getImportRow, downloadLastCsv, commonUploads, submodules } =
  useModuleConfig({
    module: props.module,
    selectedYear: props.selectedYear,
  });

const { recalcTypeRunning, getRecalcStatus, triggerTypeRecalculation } =
  useRecalculation({
    selectedYear: props.selectedYear,
  });
</script>

<template>
  <div
    :style="
      !props.isModuleEnabled ? 'opacity: 0.45; pointer-events: none' : undefined
    "
  >
    <q-separator class="q-my-xs" />

    <template v-if="commonUploads.length">
      <div
        v-for="common in commonUploads"
        :key="common.key"
        class="q-mx-lg q-pt-md"
      >
        <div v-if="common.headerIcon || common.descriptionKey" class="q-px-xs">
          <div class="row items-center q-mb-xs">
            <q-icon
              v-if="common.headerIcon"
              :name="common.headerIcon"
              color="accent"
              size="xs"
              class="q-mr-sm"
            />
            <div class="text-body1 text-weight-medium">
              {{ $t(common.labelKey) }}
            </div>
          </div>
          <div
            v-if="common.descriptionKey"
            class="text-body2 text-secondary q-mb-sm"
          >
            {{ $t(common.descriptionKey) }}
          </div>
        </div>
        <div v-else class="text-body2 text-weight-medium q-mb-sm q-px-xs">
          {{ $t(common.labelKey) }}
        </div>
        <div class="row q-pb-md" style="gap: 1rem">
          <UploadCardData
            v-if="getImportRow(common).hasData"
            :row="getImportRow(common)"
            :recalc-running="
              recalcTypeRunning[
                `${common.moduleTypeId}-${common.dataEntryTypeId}`
              ]
            "
            :recalc-status="getRecalcStatus(common)"
            @upload="(row) => emit('dataUpload', row, TargetType.DATA_ENTRIES)"
            @download="downloadLastCsv"
            @recalculate="() => triggerTypeRecalculation(common)"
          />

          <UploadCardFactors
            v-if="getImportRow(common).hasFactors"
            :row="getImportRow(common)"
            @upload="(row) => emit('factorUpload', row, TargetType.FACTORS)"
            @download="downloadLastCsv"
            @recalculate="() => triggerTypeRecalculation(common)"
          />
        </div>
      </div>
      <q-separator v-if="submodules.length > 0" class="q-my-xs" />
    </template>

    <template v-if="submodules.length > 0">
      <div class="q-px-lg q-pt-md q-pb-sm">
        <div class="row items-center q-mb-xs">
          <q-icon name="o_view_cozy" color="accent" size="xs" class="q-mr-sm" />
          <div class="text-body1 text-weight-medium">
            {{ $t('data_management_submodules_configuration_title') }}
          </div>
        </div>
        <div class="text-body2 text-secondary">
          {{ $t('data_management_submodules_configuration_description') }}
        </div>
      </div>
      <div class="q-mx-lg q-mb-lg column q-gutter-y-sm">
        <slot name="submodules"></slot>
      </div>
    </template>
  </div>
</template>

<style scoped></style>
