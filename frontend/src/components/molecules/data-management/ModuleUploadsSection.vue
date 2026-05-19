<script setup lang="ts">
import { computed, inject, type ComputedRef } from 'vue';
import type { PipelineProgress } from 'src/stores/pipelineStream';
import { useModuleConfig } from 'src/composables/useModuleConfig';
import { useRecalculation } from 'src/composables/useRecalculation';
import {
  useBackofficeDataManagement,
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import UploadCardData from 'src/components/molecules/data-management/UploadCardData.vue';
import UploadCardFactors from 'src/components/molecules/data-management/UploadCardFactors.vue';

interface Props {
  module: string;
  selectedYear: number;
  isModuleEnabled: boolean;
}

const props = defineProps<Props>();

const openDataEntryDialog = inject<
  (row: ImportRow, targetType: TargetType | null) => void
>('openDataEntryDialog')!;

const { getImportRow, downloadLastCsv, commonUploads, submodules } =
  useModuleConfig({
    module: props.module,
    selectedYear: props.selectedYear,
  });

const { recalcTypeRunning, getRecalcStatus, triggerTypeRecalculation } =
  useRecalculation({
    selectedYear: props.selectedYear,
  });

// Issue #1219 — the module's authoritative pipeline progress, provided
// by ModuleConfig (the single SSE subscriber). Shared by every card in
// the module: the recalc/aggregation pipeline is module-scoped.
const injectedPipelineProgress =
  inject<ComputedRef<PipelineProgress | null>>('pipelineProgress');
const pipelineProgress = computed<PipelineProgress | null>(
  () => injectedPipelineProgress?.value ?? null,
);

const backofficeStore = useBackofficeDataManagement();

async function handleCancelJob(jobId: number) {
  await backofficeStore.cancelJob(jobId, props.selectedYear);
}
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
          <UploadCardFactors
            v-if="getImportRow(common).hasFactors"
            :row="getImportRow(common)"
            :pipeline-progress="pipelineProgress"
            :on-download="downloadLastCsv"
            @upload="(row) => openDataEntryDialog(row, TargetType.FACTORS)"
            @recalculate="() => triggerTypeRecalculation(common)"
            @cancel="handleCancelJob"
          />
          <UploadCardData
            v-if="getImportRow(common).hasData"
            :row="getImportRow(common)"
            :pipeline-progress="pipelineProgress"
            :recalc-running="
              recalcTypeRunning[
                `${common.moduleTypeId}-${common.dataEntryTypeId}`
              ]
            "
            :recalc-status="getRecalcStatus(common)"
            :on-download="downloadLastCsv"
            @upload="(row) => openDataEntryDialog(row, TargetType.DATA_ENTRIES)"
            @recalculate="() => triggerTypeRecalculation(common)"
            @cancel="handleCancelJob"
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
