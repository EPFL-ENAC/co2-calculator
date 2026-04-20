<script setup lang="ts">
import { ref, onMounted, watch, provide } from 'vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { useModuleConfig } from 'src/composables/useModuleConfig';
import { useRecalculation } from 'src/composables/useRecalculation';
import { useYearConfigStore } from 'src/stores/yearConfig';
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

const { getModuleTypeIdFromName, isModuleEnabled, isModuleIncomplete } =
  useModuleConfig({
    module: props.module,
    selectedYear: props.selectedYear,
  });

const {
  recalculationStatus,
  recalcRunning,
  recalcTypeRunning,
  refreshRecalculationStatus,
  getRecalcStatus,
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
  const yearConfigStore = useYearConfigStore();
  await yearConfigStore.fetchConfig(props.selectedYear);
  await refreshRecalculationStatus();
}

async function handleJobProgressing() {
  const yearConfigStore = useYearConfigStore();
  await yearConfigStore.fetchConfig(props.selectedYear);
}

provide('openDataEntryDialog', openDataEntryDialog);
provide('getRecalcStatus', getRecalcStatus);
provide('refreshRecalculationStatus', refreshRecalculationStatus);
provide('handleJobCompleted', handleJobCompleted);
provide('handleJobProgressing', handleJobProgressing);
provide('recalcTypeRunning', recalcTypeRunning);
provide('triggerTypeRecalculation', triggerTypeRecalculation);

onMounted(() => {
  void refreshRecalculationStatus();
});

watch(
  () => props.selectedYear,
  () => {
    void refreshRecalculationStatus();
  },
);

defineExpose({ refreshRecalculationStatus });
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
                recalculationStatus[getModuleTypeIdFromName(module)]
                  ?.needs_recalculation
              "
              outline
              rounded
              color="warning"
              class="text-weight-medium"
              :label="$t('data_management_recalculation_needed')"
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
                recalculationStatus[getModuleTypeIdFromName(module)]
                  ?.needs_recalculation
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

      <ModuleConfigSection :module="module" />

      <ModuleUploadsSection
        :module="module"
        :selected-year="selectedYear"
        :is-module-enabled="isModuleEnabled(module)"
        @data-upload="openDataEntryDialog($event, TargetType.DATA_ENTRIES)"
        @factor-upload="openDataEntryDialog($event, TargetType.FACTORS)"
        @download="(row, targetType) => {}"
        @recalculate="(sub) => triggerTypeRecalculation(sub)"
        @job-completed="handleJobCompleted"
        @job-progressing="handleJobProgressing"
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
