<script lang="ts" setup>
import { ref, computed, watch } from 'vue';
import {
  useYearConfigStore,
  type ReductionObjectiveGoal,
} from 'src/stores/yearConfig';
import { Notify, Loading } from 'quasar';
import { useI18n } from 'vue-i18n';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

const props = defineProps<{
  selectedYear: number;
}>();

const yearConfigStore = useYearConfigStore();
const { t: $t } = useI18n();

const reductionObjectivesExpanded = ref(false);

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

/** True when at least one goal has meaningful data filled. */
const hasReductionGoals = computed(() =>
  localGoals.value.some((g) => g.target_year > 0 && g.reference_year > 0),
);

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

/** File refs for reduction objective CSV uploads. */
const footprintFile = ref<File | null>(null);
const populationFile = ref<File | null>(null);
const scenariosFile = ref<File | null>(null);

/** Uploaded file names derived from the store. */
const uploadedFileNames = computed(() => {
  const files = yearConfigStore.config?.config?.reduction_objectives?.files;
  return {
    footprint: files?.institutional_footprint?.filename ?? null,
    population: files?.population_projections?.filename ?? null,
    scenarios: files?.unit_scenarios?.filename ?? null,
  };
});

/** Handle a reduction-objective file upload. */
async function handleReductionFileUpload(
  category: 'footprint' | 'population' | 'scenarios',
  file: File | null,
): Promise<void> {
  if (!file) return;
  Loading.show({ message: $t('uploading_file') });
  try {
    await yearConfigStore.uploadFile(props.selectedYear, category, file);
    if (category === 'footprint') footprintFile.value = null;
    if (category === 'population') populationFile.value = null;
    if (category === 'scenarios') scenariosFile.value = null;
    Notify.create({ type: 'positive', message: $t('file_upload_success') });
  } catch {
    Notify.create({ type: 'negative', message: $t('file_upload_error') });
  } finally {
    Loading.hide();
  }
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
              v-if="!hasReductionGoals"
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
      <q-card flat class="q-pa-none row">
        <q-card
          flat
          class="col q-px-lg q-py-xl"
          style="border-right: 1px solid #d5d5d5"
        >
          <div class="row items-start align-center q-my-xs">
            <q-icon name="barefoot" color="accent" size="xs" class="q-mr-sm" />
            <div class="text-body1 text-weight-medium">
              {{ $t('data_management_institution_carbon_footprint_title') }}
            </div>
          </div>
          <div class="text-body2 text-secondary">
            {{ $t('data_management_institution_carbon_footprint_description') }}
          </div>
          <div
            v-if="uploadedFileNames.footprint"
            class="text-caption text-positive q-mt-sm"
          >
            <q-icon name="check" /> {{ uploadedFileNames.footprint }}
          </div>
          <div class="row q-gutter-md q-mt-lg">
            <q-file
              v-model="footprintFile"
              outlined
              dense
              accept=".csv"
              :label="$t('common_upload_csv')"
              class="col"
              @update:model-value="
                handleReductionFileUpload('footprint', $event)
              "
            >
              <template #prepend>
                <q-icon name="o_upload" />
              </template>
            </q-file>
          </div>
        </q-card>
        <q-card
          flat
          class="col q-px-lg q-py-xl"
          style="border-right: 1px solid #d5d5d5"
        >
          <div class="row items-start align-center q-mb-xs">
            <q-icon
              name="o_groups_2"
              color="accent"
              size="xs"
              class="q-mr-sm"
            />
            <div class="text-body1 text-weight-medium">
              {{ $t('data_management_population_projections_title') }}
            </div>
          </div>
          <div class="text-body2 text-secondary">
            {{ $t('data_management_population_projections_description') }}
          </div>
          <div
            v-if="uploadedFileNames.population"
            class="text-caption text-positive q-mt-sm"
          >
            <q-icon name="check" /> {{ uploadedFileNames.population }}
          </div>
          <div class="row q-gutter-md q-mt-lg">
            <q-file
              v-model="populationFile"
              outlined
              dense
              accept=".csv"
              :label="$t('common_upload_csv')"
              class="col"
              @update:model-value="
                handleReductionFileUpload('population', $event)
              "
            >
              <template #prepend>
                <q-icon name="o_upload" />
              </template>
            </q-file>
          </div>
        </q-card>
        <q-card flat class="col q-px-lg q-py-xl border-right">
          <div class="row items-start align-center q-mb-xs">
            <q-icon
              name="o_square_foot"
              color="accent"
              size="xs"
              class="q-mr-sm"
            />
            <div class="text-body1 text-weight-medium">
              {{ $t('data_management_unit_reduction_scenarios_title') }}
            </div>
          </div>
          <div class="text-body2 text-secondary">
            {{ $t('data_management_unit_reduction_scenarios_description') }}
          </div>
          <div
            v-if="uploadedFileNames.scenarios"
            class="text-caption text-positive q-mt-sm"
          >
            <q-icon name="check" /> {{ uploadedFileNames.scenarios }}
          </div>
          <div class="row q-gutter-md q-mt-lg">
            <q-file
              v-model="scenariosFile"
              outlined
              dense
              accept=".csv"
              :label="$t('common_upload_csv')"
              class="col"
              @update:model-value="
                handleReductionFileUpload('scenarios', $event)
              "
            >
              <template #prepend>
                <q-icon name="o_upload" />
              </template>
            </q-file>
          </div>
        </q-card>
      </q-card>
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
