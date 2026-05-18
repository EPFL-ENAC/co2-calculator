<script lang="ts" setup>
import { ref, computed, watch } from 'vue';
import {
  useYearConfigStore,
  type ReductionObjectiveGoal,
  type FileMetadata,
} from 'src/stores/yearConfig';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { inject } from 'vue';
import {
  TargetType,
  type ImportRow,
  type SyncJobResponse,
} from 'src/stores/backofficeDataManagement';
import UploadCard from 'src/components/molecules/data-management/UploadCard.vue';

const props = defineProps<{
  selectedYear: number;
}>();

const yearConfigStore = useYearConfigStore();
const { t: $t } = useI18n();

const reductionObjectivesExpanded = ref(false);

const openDataEntryDialog = inject<
  (row: ImportRow, targetType: TargetType | null) => void
>('openDataEntryDialog')!;

/** Default empty goal for a slot. */
function emptyGoal(): ReductionObjectiveGoal {
  return {
    target_year: 0,
    reduction_percentage: 0,
    reference_year: 0,
  };
}

/** Local goals (3 fixed slots). Updated from store on config change. */
const localGoals = ref<ReductionObjectiveGoal[]>([
  emptyGoal(),
  emptyGoal(),
  emptyGoal(),
]);

const isSavingGoals = ref(false);

/** Sync store → local when config is fetched. Percentage is converted to 0–100 for display. */
watch(
  () => yearConfigStore.config?.config?.reduction_objectives?.goals,
  (storeGoals) => {
    if (!storeGoals) return;
    for (let i = 0; i < 3; i++) {
      if (storeGoals[i]) {
        localGoals.value[i] = {
          ...storeGoals[i],
          reduction_percentage: storeGoals[i].reduction_percentage * 100,
        };
      } else {
        localGoals.value[i] = emptyGoal();
      }
    }
  },
  { immediate: true },
);

/** True when all mandatory fields are filled: 3 CSV files + first goal. */
const isComplete = computed(() => {
  const files = yearConfigStore.config?.config?.reduction_objectives?.files;
  return (
    !!files?.institutional_footprint &&
    !!files?.population_projections &&
    !!files?.unit_scenarios &&
    localGoals.value[0].target_year > 0 &&
    localGoals.value[0].reference_year > 0
  );
});

/** True when all filled-in goals pass validation (percentage displayed as 0–100). */
const goalsAreValid = computed(() =>
  localGoals.value.every((g) => {
    const isEmpty =
      !g.target_year && !g.reference_year && !g.reduction_percentage;
    if (isEmpty) return true;
    return (
      g.target_year > props.selectedYear &&
      g.reduction_percentage >= 0 &&
      g.reduction_percentage <= 100 &&
      g.reference_year > 0
    );
  }),
);

/** Persist all non-empty goals to the store. Converts percentage from 0–100 display to 0–1 storage. */
async function saveReductionGoals(): Promise<void> {
  const goalsToSave = localGoals.value
    .filter((g) => g.target_year > 0 && g.reference_year > 0)
    .map((g) => ({
      ...g,
      reduction_percentage: g.reduction_percentage / 100,
    }));

  isSavingGoals.value = true;
  try {
    await yearConfigStore.updateConfig(props.selectedYear, {
      config: {
        reduction_objectives: { goals: goalsToSave },
      },
    });
    Notify.create({ type: 'positive', message: $t('year_config_saved') });
  } catch {
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  } finally {
    isSavingGoals.value = false;
  }
}

/** Convert a FileMetadata entry into a minimal SyncJobResponse so UploadCard can render file info and download. */
function fileMetaToJob(
  file: FileMetadata | null | undefined,
): SyncJobResponse | undefined {
  if (!file) return undefined;
  return {
    job_id: 0,
    meta: {
      file_path: file.filename,
      processed_file_path: file.path,
      timestamp: file.uploaded_at,
      rows_processed: file.rows_processed,
    },
  };
}

function downloadFile(file: FileMetadata | null | undefined): void {
  if (!file?.path) return;
  const a = document.createElement('a');
  a.href = `/api/v1/files/${file.path}`;
  a.download = file.filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

const reductionFiles = computed(
  () => yearConfigStore.config?.config?.reduction_objectives?.files,
);

function csvButtonColor(file: FileMetadata | null | undefined): string {
  return file ? 'positive' : 'accent';
}

function csvButtonLabel(file: FileMetadata | null | undefined): string {
  return file ? $t('data_management_reupload_data') : $t('common_upload_csv');
}
</script>

<template>
  <q-card flat bordered class="q-py-none q-mb-lg">
    <q-expansion-item v-model="reductionObjectivesExpanded" expand-separator>
      <template #header>
        <q-item-section avatar>
          <ModuleIcon name="reduction-objectives" size="md" color="accent" />
        </q-item-section>
        <q-item-section>
          <div class="row items-center q-gutter-sm">
            <span class="text-h4 text-weight-medium">
              {{ $t('data_management_reduction_objectives') }}</span
            >
            <q-badge
              v-if="!isComplete"
              outline
              rounded
              color="accent"
              class="text-weight-medium"
              :label="$t('common_filter_incomplete')"
            />
          </div>
        </q-item-section>
        <q-item-section class="text-h4 text-weight-medium"> </q-item-section>
      </template>
      <q-separator />
      <!-- File Upload Section -->
      <div class="row q-pa-md q-gutter-md">
        <UploadCard
          class="col"
          :title="$t('data_management_institution_carbon_footprint_title')"
          :description="
            $t('data_management_institution_carbon_footprint_description')
          "
          :show-mandatory-indicator="true"
          :button-color="
            csvButtonColor(reductionFiles?.institutional_footprint)
          "
          :button-label="
            csvButtonLabel(reductionFiles?.institutional_footprint)
          "
          button-icon="upload"
          :row="
            {
              reductionObjectiveTypeId: 0,
              labelKey: 'data_management_institution_carbon_footprint_title',
            } as ImportRow
          "
          :target-type="TargetType.REDUCTION_OBJECTIVES"
          :last-job="fileMetaToJob(reductionFiles?.institutional_footprint)"
          @upload="openDataEntryDialog($event, TargetType.REDUCTION_OBJECTIVES)"
          @download="downloadFile(reductionFiles?.institutional_footprint)"
        />
        <UploadCard
          class="col"
          :title="$t('data_management_population_projections_title')"
          :description="
            $t('data_management_population_projections_description')
          "
          :show-mandatory-indicator="true"
          :button-color="csvButtonColor(reductionFiles?.population_projections)"
          :button-label="csvButtonLabel(reductionFiles?.population_projections)"
          button-icon="upload"
          :row="
            {
              reductionObjectiveTypeId: 1,
              labelKey: 'data_management_population_projections_title',
            } as ImportRow
          "
          :target-type="TargetType.REDUCTION_OBJECTIVES"
          :last-job="fileMetaToJob(reductionFiles?.population_projections)"
          @upload="openDataEntryDialog($event, TargetType.REDUCTION_OBJECTIVES)"
          @download="downloadFile(reductionFiles?.population_projections)"
        />
        <UploadCard
          class="col"
          :title="$t('data_management_unit_reduction_scenarios_title')"
          :description="
            $t('data_management_unit_reduction_scenarios_description')
          "
          :show-mandatory-indicator="true"
          :button-color="csvButtonColor(reductionFiles?.unit_scenarios)"
          :button-label="csvButtonLabel(reductionFiles?.unit_scenarios)"
          button-icon="upload"
          :row="
            {
              reductionObjectiveTypeId: 2,
              labelKey: 'data_management_unit_reduction_scenarios_title',
            } as ImportRow
          "
          :target-type="TargetType.REDUCTION_OBJECTIVES"
          :last-job="fileMetaToJob(reductionFiles?.unit_scenarios)"
          @upload="openDataEntryDialog($event, TargetType.REDUCTION_OBJECTIVES)"
          @download="downloadFile(reductionFiles?.unit_scenarios)"
        />
      </div>
      <q-separator />
      <!-- Goals Section -->
      <q-item-section class="q-pt-xl q-pb-sm q-px-md">
        <div class="row items-start align-center q-mb-xs">
          <q-icon name="adjust" color="accent" size="xs" class="q-mr-sm" />
          <div class="text-body1 text-weight-medium">
            {{ $t('data_management_define_reduction_objectives_title') }}
          </div>
        </div>
        <div class="text-body2 text-secondary">
          {{ $t('data_management_define_reduction_objectives_description') }}
        </div>
      </q-item-section>
      <div class="row q-my-sm">
        <!-- First Goal (mandatory) -->
        <q-card flat bordered class="q-pa-md q-ma-md col">
          <div class="row justify-between items-center">
            <div class="text-body2 text-weight-medium">
              {{ $t('data_management_first_reduction_objectives') }}
            </div>
            <div class="text-body2 text-secondary">
              <span class="text-negative">*</span>{{ $t('common_mandatory') }}
            </div>
          </div>
          <div class="col full-width q-mt-lg q-gutter-md">
            <q-input
              v-model.number="localGoals[0].target_year"
              outlined
              dense
              type="number"
              class="full-width"
              :label="
                $t('data_management_first_reduction_objectives_target_year')
              "
              placeholder="2030"
              :rules="[
                (v: number) =>
                  !v || v > selectedYear || $t('year_config_target_year_error'),
              ]"
            />
            <q-input
              v-model.number="localGoals[0].reduction_percentage"
              outlined
              dense
              type="number"
              class="full-width"
              :label="$t('data_management_reduction_objectives_reduction_goal')"
              placeholder="40"
              hint="0 – 100"
              :rules="[
                (v: number) =>
                  (!v && v !== undefined) ||
                  (v >= 0 && v <= 100) ||
                  $t('year_config_percentage_error'),
              ]"
            />
            <q-input
              v-model.number="localGoals[0].reference_year"
              outlined
              dense
              type="number"
              class="full-width"
              :label="$t('data_management_reduction_objectives_reference_year')"
              placeholder="2019"
              :rules="[
                (v: number) =>
                  !v || v > 0 || $t('year_config_reference_year_error'),
              ]"
            />
          </div>
        </q-card>
        <!-- Second Goal -->
        <q-card flat bordered class="q-pa-md q-ma-md col">
          <div class="text-body2 text-weight-medium">
            {{ $t('data_management_second_reduction_objectives') }}
          </div>
          <div class="col full-width q-mt-lg q-gutter-md">
            <q-input
              v-model.number="localGoals[1].target_year"
              outlined
              dense
              type="number"
              class="full-width"
              :label="
                $t('data_management_first_reduction_objectives_target_year')
              "
              placeholder="2030"
              :rules="[
                (v: number) =>
                  !v || v > selectedYear || $t('year_config_target_year_error'),
              ]"
            />
            <q-input
              v-model.number="localGoals[1].reduction_percentage"
              outlined
              dense
              type="number"
              class="full-width"
              :label="$t('data_management_reduction_objectives_reduction_goal')"
              placeholder="40"
              hint="0 – 100"
              :rules="[
                (v: number) =>
                  (!v && v !== undefined) ||
                  (v >= 0 && v <= 100) ||
                  $t('year_config_percentage_error'),
              ]"
            />
            <q-input
              v-model.number="localGoals[1].reference_year"
              outlined
              dense
              type="number"
              class="full-width"
              :label="$t('data_management_reduction_objectives_reference_year')"
              placeholder="2019"
              :rules="[
                (v: number) =>
                  !v || v > 0 || $t('year_config_reference_year_error'),
              ]"
            />
          </div>
        </q-card>
        <!-- Third Goal -->
        <q-card flat bordered class="q-pa-md q-ma-md col">
          <div class="text-body2 text-weight-medium">
            {{ $t('data_management_third_reduction_objectives') }}
          </div>
          <div class="col full-width q-mt-lg q-gutter-md">
            <q-input
              v-model.number="localGoals[2].target_year"
              outlined
              dense
              type="number"
              class="full-width"
              :label="
                $t('data_management_first_reduction_objectives_target_year')
              "
              placeholder="2030"
              :rules="[
                (v: number) =>
                  !v || v > selectedYear || $t('year_config_target_year_error'),
              ]"
            />
            <q-input
              v-model.number="localGoals[2].reduction_percentage"
              outlined
              dense
              type="number"
              class="full-width"
              :label="$t('data_management_reduction_objectives_reduction_goal')"
              placeholder="40"
              hint="0 – 100"
              :rules="[
                (v: number) =>
                  (!v && v !== undefined) ||
                  (v >= 0 && v <= 100) ||
                  $t('year_config_percentage_error'),
              ]"
            />
            <q-input
              v-model.number="localGoals[2].reference_year"
              outlined
              dense
              type="number"
              class="full-width"
              :label="$t('data_management_reduction_objectives_reference_year')"
              placeholder="2019"
              :rules="[
                (v: number) =>
                  !v || v > 0 || $t('year_config_reference_year_error'),
              ]"
            />
          </div>
        </q-card>
      </div>
      <q-btn
        color="accent"
        size="md"
        :label="$t('common_save')"
        :loading="isSavingGoals"
        :disable="!goalsAreValid"
        class="q-mb-md q-ml-md text-weight-medium text-capitalize"
        @click="saveReductionGoals"
      />
    </q-expansion-item>
  </q-card>
</template>
