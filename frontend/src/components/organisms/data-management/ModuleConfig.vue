<script setup lang="ts">
import { computed, ref, provide, watch } from 'vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { useModuleConfig } from 'src/composables/useModuleConfig';
import { useRecalculation } from 'src/composables/useRecalculation';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { usePipelineStream } from 'src/composables/usePipelineStream';
import {
  TargetType,
  type ImportRow,
} from 'src/stores/backofficeDataManagement';
import DataEntryDialog from 'src/components/organisms/data-management/DataEntryDialog.vue';
import ModuleRecalculationDialog from 'src/components/molecules/data-management/ModuleRecalculationDialog.vue';
import ModuleConfigSection from 'src/components/molecules/data-management/ModuleConfigSection.vue';
import ModuleUploadsSection from 'src/components/molecules/data-management/ModuleUploadsSection.vue';
import SubmoduleConfig from 'src/components/organisms/data-management/SubmoduleConfig.vue';

interface Props {
  module: string;
  selectedYear: number;
}

const props = defineProps<Props>();

const yearConfigStore = useYearConfigStore();

const { getModuleTypeIdFromName, isModuleEnabled, isModuleIncomplete } =
  useModuleConfig({
    module: props.module,
    selectedYear: props.selectedYear,
  });

// Plan 310-D — pipeline-scoped SSE consumer drives the
// "Recalculating..." badge.  ``current_pipeline_id`` rides on the
// per-module ``recalculationStatus`` entry (extended in PR #1054
// backend half) — null when no active pipeline, set to the
// pipeline_id while a bulk chain is in flight.
const { subscribe, unsubscribe, isFinishedFor, hasErrorFor } =
  usePipelineStream();

const currentPipelineId = computed<string | null>(() => {
  const moduleTypeId = getModuleTypeIdFromName(props.module);
  return (
    yearConfigStore.recalculationStatus[moduleTypeId]?.current_pipeline_id ??
    null
  );
});

const isRecalculating = computed<boolean>(() => {
  const id = currentPipelineId.value;
  if (!id) return false;
  // Active until the SSE stream signals finish — even if a previous
  // entry on this id is finished, the badge clears via the watch
  // below which refetches the year config.
  return !isFinishedFor(id).value;
});

const hasRecalcFailure = computed<boolean>(() => {
  const id = currentPipelineId.value;
  if (!id) return false;
  return hasErrorFor(id).value;
});

// Wire the SSE subscription to the reactive pipeline_id.  When it
// transitions ``null → uuid`` we subscribe; ``uuid → null`` (badge
// cleared by the year-config refetch) → unsubscribe; ``uuidA →
// uuidB`` (rare — new pipeline started while old finished) → switch.
let lastSubscribedId: string | null = null;
watch(
  currentPipelineId,
  async (next) => {
    if (lastSubscribedId === next) return;
    if (lastSubscribedId) unsubscribe(lastSubscribedId);
    lastSubscribedId = next;
    if (next) await subscribe(next);
  },
  { immediate: true },
);

// When the pipeline reports finished, refetch the year config so
// ``current_pipeline_id`` clears (or, on error, stays set with the
// failure-state metadata for the future retry button).
watch(
  () =>
    currentPipelineId.value
      ? isFinishedFor(currentPipelineId.value).value
      : false,
  async (finished, wasFinished) => {
    if (finished && !wasFinished && !hasRecalcFailure.value) {
      await yearConfigStore.fetchConfig(props.selectedYear);
    }
  },
);

const {
  recalcRunning,
  recalcTypeRunning,
  confirmModuleRecalculation,
  triggerTypeRecalculation,
  staleTypesForModule,
} = useRecalculation({
  selectedYear: props.selectedYear,
});

const showDataEntryDialog = ref(false);
const dialogCurrentRow = ref<ImportRow | null>(null);
const dialogTargetType = ref<TargetType | null>(null);

const showRecalcDialog = ref(false);
const recalcDialogModuleTypeId = ref<number | null>(null);
const recalcOnlyStale = ref(true);

function openDataEntryDialog(row: ImportRow, targetType: TargetType | null) {
  dialogCurrentRow.value = row;
  dialogTargetType.value = targetType;
  showDataEntryDialog.value = true;
}

function openRecalcDialog(moduleTypeId: number) {
  recalcDialogModuleTypeId.value = moduleTypeId;
  recalcOnlyStale.value = true;
  showRecalcDialog.value = true;
}

async function handleJobCompleted() {
  await yearConfigStore.fetchConfig(props.selectedYear);
}

async function handleJobProgressing() {
  await yearConfigStore.fetchConfig(props.selectedYear);
}

provide('openDataEntryDialog', openDataEntryDialog);
provide('getRecalcStatus', yearConfigStore.getRecalcStatus);
provide('handleJobCompleted', handleJobCompleted);
provide('handleJobProgressing', handleJobProgressing);
provide('recalcTypeRunning', recalcTypeRunning);
provide('triggerTypeRecalculation', triggerTypeRecalculation);
</script>

<template>
  <q-card flat bordered class="q-pa-none q-mb-lg">
    <q-expansion-item expand-separator>
      <template #header>
        <q-item-section avatar>
          <ModuleIcon :name="module" size="md" color="accent" />
        </q-item-section>
        <q-item-section>
          <div class="row items-center q-gutter-sm">
            <span class="text-h4 text-weight-medium">{{ $t(module) }}</span>
            <q-badge
              v-if="!isModuleEnabled(module)"
              outline
              rounded
              color="grey"
              class="text-weight-medium"
              :label="$t('common_disabled')"
            />
            <q-badge
              v-else-if="isModuleIncomplete(module)"
              outline
              rounded
              color="accent"
              class="text-weight-medium"
              :label="$t('common_filter_incomplete')"
            />
            <q-badge
              v-if="
                yearConfigStore.recalculationStatus[
                  getModuleTypeIdFromName(module)
                ]?.needs_recalculation
              "
              outline
              rounded
              color="warning"
              class="text-weight-medium"
              :label="$t('data_management_recalculation_needed')"
            />
            <!--
              Plan 310-D — "Recalculating..." badge for in-flight bulk
              pipelines.  Drives off ``current_pipeline_id`` on the
              per-module recalc-status entry (set when an active
              NOT_STARTED/QUEUED/RUNNING aggregation pipeline touches
              this module's year), with the SSE composable controlling
              the live state.
            -->
            <q-badge
              v-if="isRecalculating"
              outline
              rounded
              color="info"
              class="text-weight-medium"
              :label="$t('data_management_pipeline_recalculating')"
            />
            <q-badge
              v-else-if="hasRecalcFailure"
              outline
              rounded
              color="negative"
              class="text-weight-medium"
              :label="$t('data_management_pipeline_failed')"
            />
          </div>
        </q-item-section>
        <q-item-section side>
          <div class="row items-center q-gutter-sm">
            <q-spinner-rings
              v-if="recalcRunning[getModuleTypeIdFromName(module)]"
              color="grey"
              size="sm"
            />
            <q-btn
              v-if="
                yearConfigStore.recalculationStatus[
                  getModuleTypeIdFromName(module)
                ]?.needs_recalculation
              "
              flat
              dense
              size="sm"
              icon="refresh"
              color="accent"
              :label="$t('data_management_recalculate_emissions')"
              @click.stop="openRecalcDialog(getModuleTypeIdFromName(module))"
            />
          </div>
        </q-item-section>
      </template>

      <ModuleConfigSection :module="module" :selected-year="selectedYear" />

      <ModuleUploadsSection
        :module="module"
        :selected-year="selectedYear"
        :is-module-enabled="isModuleEnabled(module)"
      >
        <template #submodules>
          <SubmoduleConfig :module="module" :selected-year="selectedYear" />
        </template>
      </ModuleUploadsSection>
    </q-expansion-item>
  </q-card>

  <DataEntryDialog
    v-model="showDataEntryDialog"
    :row="dialogCurrentRow || ({} as ImportRow)"
    :year="selectedYear"
    :target-type="dialogTargetType ?? TargetType.DATA_ENTRIES"
    @completed="handleJobCompleted"
    @progressing="handleJobProgressing"
  />

  <ModuleRecalculationDialog
    v-model="showRecalcDialog"
    :module-type-id="recalcDialogModuleTypeId"
    :stale-types="staleTypesForModule(recalcDialogModuleTypeId || 0)"
    :only-stale="recalcOnlyStale"
    @confirm="confirmModuleRecalculation(recalcDialogModuleTypeId!)"
    @cancel="showRecalcDialog = false"
  />
</template>

<style scoped></style>
