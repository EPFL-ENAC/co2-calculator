<script setup lang="ts">
import { ref, inject, type Ref } from 'vue';
import { useSubmoduleConfig } from 'src/composables/useSubmoduleConfig';
import { useRecalculation } from 'src/composables/useRecalculation';
import {
  useBackofficeDataManagement,
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import type { SubmoduleConfig } from 'src/constant/backoffice-module-config';
import UploadCardData from 'src/components/molecules/data-management/UploadCardData.vue';
import UploadCardFactors from 'src/components/molecules/data-management/UploadCardFactors.vue';
import UploadCardReferences from 'src/components/molecules/data-management/UploadCardReferences.vue';
import ComputedFactorDialog from 'src/components/molecules/data-management/ComputedFactorDialog.vue';

interface Props {
  submodule: SubmoduleConfig;
  selectedYear: number;
}

const props = defineProps<Props>();

const {
  isSubmoduleEnabled,
  isSubmoduleIncomplete,
  getImportRow,
  submoduleShowsImportRow,
  downloadLastCsv,
  updateSubmoduleEnabled,
  getSubmoduleThreshold,
  updateSubmoduleThreshold,
  computedFactorRunning,
  anyComputedFactorRunning,
  confirmComputedFactorSync,
} = useSubmoduleConfig({
  module: '',
  selectedYear: props.selectedYear,
});

const { getRecalcStatus } = useRecalculation({
  selectedYear: props.selectedYear,
});

const backofficeStore = useBackofficeDataManagement();

const triggerTypeRecalculation = inject<
  (sub: SubmoduleConfig) => Promise<void>
>('triggerTypeRecalculation')!;

const openDataEntryDialog = inject<
  (row: ImportRow, targetType: TargetType | null) => void
>('openDataEntryDialog')!;

const handleJobCompleted = inject<() => Promise<void>>('handleJobCompleted')!;
const handleJobProgressing = inject<() => Promise<void>>(
  'handleJobProgressing',
)!;
const recalcTypeRunning =
  inject<Ref<Record<string, boolean>>>('recalcTypeRunning')!;

const showComputedFactorConfirm = ref(false);

function openComputedFactorConfirm() {
  showComputedFactorConfirm.value = true;
}

async function handleComputedFactorConfirm() {
  await confirmComputedFactorSync(props.submodule, handleJobCompleted);
}

async function handleReferenceCompleted() {
  await handleJobCompleted();
}

async function handleReferenceProgressing() {
  await handleJobProgressing();
}

async function handleCancelJob(jobId: number) {
  await backofficeStore.cancelJob(jobId, props.selectedYear);
  await handleJobCompleted();
}
</script>

<template>
  <q-expansion-item
    :key="submodule.key"
    expand-separator
    class="bg-white rounded-borders"
    style="border: 1px solid rgba(0, 0, 0, 0.12)"
  >
    <template #header>
      <q-item-section>
        <div class="row items-center q-gutter-sm">
          <span
            class="text-body2 text-weight-medium"
            :class="!isSubmoduleEnabled(submodule) ? 'text-grey-6' : ''"
            >{{ $t(submodule.labelKey) }}</span
          >
          <q-badge
            v-if="
              submodule.dataEntryTypeId !== undefined &&
              getRecalcStatus(submodule)?.needs_recalculation
            "
            outline
            rounded
            color="warning"
            class="text-weight-medium"
            :label="$t('data_management_recalculation_needed')"
          />
          <q-badge
            v-if="
              isSubmoduleEnabled(submodule) && isSubmoduleIncomplete(submodule)
            "
            outline
            rounded
            color="accent"
            class="text-weight-medium"
            :label="$t('common_filter_incomplete')"
          />
        </div>
      </q-item-section>
    </template>
    <q-separator class="q-mb-xs" />

    <template v-if="!submodule.factorsOnly">
      <q-card flat class="col q-px-lg q-pt-lg q-pb-md">
        <div class="row items-center q-mb-xs">
          <q-icon
            name="power_settings_new"
            color="accent"
            size="xs"
            class="q-mr-sm"
          />
          <div class="text-body2 text-weight-medium">
            {{ $t('data_management_submodule_activation_title') }}
          </div>
        </div>
        <div class="text-caption text-secondary q-mb-sm">
          {{ $t('data_management_submodule_activation_description') }}
        </div>
        <q-toggle
          :model-value="isSubmoduleEnabled(submodule)"
          color="accent"
          keep-color
          size="md"
          @update:model-value="
            (val: boolean) => updateSubmoduleEnabled(submodule, val)
          "
        />
      </q-card>
      <q-separator class="q-my-xs" />
      <q-card
        flat
        class="col q-px-lg q-pt-lg q-pb-md"
        :style="
          !isSubmoduleEnabled(submodule)
            ? 'opacity: 0.45; pointer-events: none'
            : undefined
        "
      >
        <div class="row items-center q-mb-xs">
          <q-icon
            name="legend_toggle"
            color="accent"
            size="xs"
            class="q-mr-sm"
          />
          <div class="text-body2 text-weight-medium">
            {{ $t('data_management_threshold_title') }}
          </div>
        </div>
        <div class="text-caption text-secondary q-mb-sm">
          {{ $t('data_management_threshold_description') }}
        </div>
        <q-input
          :model-value="getSubmoduleThreshold(submodule)"
          type="number"
          dense
          outlined
          size="md"
          :debounce="600"
          :suffix="$t('tco2eq')"
          :placeholder="$t('no_threshold')"
          style="max-width: 500px"
          @update:model-value="
            (val: string | number | null) =>
              updateSubmoduleThreshold(
                submodule,
                val === '' || val === null ? null : Number(val),
              )
          "
        />
      </q-card>
      <q-separator v-if="submoduleShowsImportRow(submodule)" class="q-my-xs" />
    </template>

    <div
      v-if="submoduleShowsImportRow(submodule)"
      class="row q-pa-md"
      :style="[
        { gap: '1rem' },
        !isSubmoduleEnabled(submodule)
          ? { opacity: 0.45, pointerEvents: 'none' }
          : {},
      ]"
    >
      <UploadCardData
        v-if="getImportRow(submodule).hasData"
        :row="getImportRow(submodule)"
        :recalc-running="
          recalcTypeRunning[
            `${submodule.moduleTypeId}-${submodule.dataEntryTypeId}`
          ]
        "
        :recalc-status="getRecalcStatus(submodule)"
        :on-download="downloadLastCsv"
        @upload="(row) => openDataEntryDialog(row, TargetType.DATA_ENTRIES)"
        @recalculate="() => triggerTypeRecalculation(submodule)"
        @cancel="handleCancelJob"
      />
      <UploadCardFactors
        v-if="getImportRow(submodule).hasFactors"
        :row="getImportRow(submodule)"
        :module="submodule.key"
        :computed-factor-running="computedFactorRunning[submodule.key]"
        :any-computed-factor-running="anyComputedFactorRunning"
        :on-download="
          (e, y) => {
            downloadLastCsv(e, y);
          }
        "
        @upload="(row) => openDataEntryDialog(row, TargetType.FACTORS)"
        @recalculate="() => triggerTypeRecalculation(submodule)"
        @compute-factors="openComputedFactorConfirm"
        @cancel="handleCancelJob"
      />

      <UploadCardReferences
        v-if="getImportRow(submodule).hasOtherUpload"
        :row="getImportRow(submodule)"
        :year="selectedYear"
        @completed="handleReferenceCompleted"
        @progressing="handleReferenceProgressing"
      />
    </div>

    <ComputedFactorDialog
      v-model="showComputedFactorConfirm"
      @confirm="handleComputedFactorConfirm"
      @cancel="showComputedFactorConfirm = false"
    />
  </q-expansion-item>
</template>

<style scoped></style>
