<script setup lang="ts">
import { ref, watch } from 'vue';
import {
  useYearConfigStore,
  type ReductionObjectiveGoal,
} from 'src/stores/yearConfig';
import { Notify, Loading } from 'quasar';
import { useI18n } from 'vue-i18n';

interface Props {
  year: number;
}

const props = defineProps<Props>();
const { t: $t } = useI18n();
const yearConfigStore = useYearConfigStore();

const localGoals = ref<ReductionObjectiveGoal[]>([
  {
    target_year: new Date().getFullYear() + 5,
    reduction_percentage: 0.4,
    reference_year: props.year,
  },
]);

const isUploading = ref(false);
const uploadedFiles = ref({
  footprint: null as string | null,
  population: null as string | null,
  scenarios: null as string | null,
});

// Load configuration
const loadConfig = async () => {
  try {
    const response = await yearConfigStore.fetchConfig(props.year);
    if (response.config.reduction_objectives) {
      // Load files
      if (response.config.reduction_objectives.files.institutional_footprint) {
        uploadedFiles.value.footprint =
          response.config.reduction_objectives.files.institutional_footprint.filename;
      }
      if (response.config.reduction_objectives.files.population_projections) {
        uploadedFiles.value.population =
          response.config.reduction_objectives.files.population_projections.filename;
      }
      if (response.config.reduction_objectives.files.unit_scenarios) {
        uploadedFiles.value.scenarios =
          response.config.reduction_objectives.files.unit_scenarios.filename;
      }

      // Load goals
      if (response.config.reduction_objectives.goals.length > 0) {
        localGoals.value = [...response.config.reduction_objectives.goals];
      }
    }
  } catch (err) {
    console.error('Failed to load reduction objectives:', err);
  }
};

// Save goals
const saveGoals = async () => {
  try {
    // Validate goals
    for (const goal of localGoals.value) {
      if (goal.target_year <= props.year) {
        Notify.create({
          type: 'negative',
          message: $t('year_config_target_year_error'),
        });
        return;
      }
      if (goal.reduction_percentage < 0 || goal.reduction_percentage > 1) {
        Notify.create({
          type: 'negative',
          message: $t('year_config_percentage_error'),
        });
        return;
      }
    }

    await yearConfigStore.updateConfig(props.year, {
      config: {
        reduction_objectives: {
          goals: localGoals.value,
        },
      },
    });

    Notify.create({
      type: 'positive',
      message: $t('year_config_saved'),
    });
  } catch (err) {
    console.error('Failed to save goals:', err);
    Notify.create({
      type: 'negative',
      message: $t('year_config_save_error'),
    });
  }
};

// Handle file upload
const handleFileUpload = async (
  category: 'footprint' | 'population' | 'scenarios',
  file: File,
) => {
  isUploading.value = true;
  Loading.show({ message: $t('uploading_file') });

  try {
    await yearConfigStore.uploadFile(props.year, category, file);

    // Update local state
    if (category === 'footprint') uploadedFiles.value.footprint = file.name;
    if (category === 'population') uploadedFiles.value.population = file.name;
    if (category === 'scenarios') uploadedFiles.value.scenarios = file.name;

    Notify.create({
      type: 'positive',
      message: $t('file_upload_success'),
    });
  } catch (err) {
    console.error('File upload failed:', err);
    Notify.create({
      type: 'negative',
      message: $t('file_upload_error'),
    });
  } finally {
    Loading.hide();
    isUploading.value = false;
  }
};

// Add new goal
const addGoal = () => {
  localGoals.value.push({
    target_year: new Date().getFullYear() + 5,
    reduction_percentage: 0.4,
    reference_year: props.year,
  });
};

// Remove goal
const removeGoal = (index: number) => {
  localGoals.value.splice(index, 1);
  saveGoals();
};

// Watch for year changes
watch(
  () => props.year,
  () => {
    loadConfig();
  },
  { immediate: true },
);
</script>

<template>
  <div>
    <div class="text-h5 q-mb-md">{{ $t('reduction_objectives') }}</div>

    <q-card flat bordered class="q-pa-md q-mb-lg">
      <div class="text-subtitle1 q-mb-md">{{ $t('reference_files') }}</div>

      <div class="row q-gutter-md">
        <!-- Footprint file -->
        <div class="col-12 col-md-4">
          <q-card-section>
            <div class="text-body1">{{ $t('institutional_footprint') }}</div>
            <q-file
              outlined
              :label="$t('upload_file')"
              :loading="isUploading"
              @update:model-value="handleFileUpload('footprint', $event)"
            >
              <template #prepend>
                <q-icon name="upload" />
              </template>
            </q-file>
            <div
              v-if="uploadedFiles.footprint"
              class="text-caption text-positive q-mt-sm"
            >
              <q-icon name="check" /> {{ uploadedFiles.footprint }}
            </div>
          </q-card-section>
        </div>

        <!-- Population file -->
        <div class="col-12 col-md-4">
          <q-card-section>
            <div class="text-body1">{{ $t('population_projections') }}</div>
            <q-file
              outlined
              :label="$t('upload_file')"
              :loading="isUploading"
              @update:model-value="handleFileUpload('population', $event)"
            >
              <template #prepend>
                <q-icon name="upload" />
              </template>
            </q-file>
            <div
              v-if="uploadedFiles.population"
              class="text-caption text-positive q-mt-sm"
            >
              <q-icon name="check" /> {{ uploadedFiles.population }}
            </div>
          </q-card-section>
        </div>

        <!-- Scenarios file -->
        <div class="col-12 col-md-4">
          <q-card-section>
            <div class="text-body1">{{ $t('unit_scenarios') }}</div>
            <q-file
              outlined
              :label="$t('upload_file')"
              :loading="isUploading"
              @update:model-value="handleFileUpload('scenarios', $event)"
            >
              <template #prepend>
                <q-icon name="upload" />
              </template>
            </q-file>
            <div
              v-if="uploadedFiles.scenarios"
              class="text-caption text-positive q-mt-sm"
            >
              <q-icon name="check" /> {{ uploadedFiles.scenarios }}
            </div>
          </q-card-section>
        </div>
      </div>
    </q-card>

    <q-card flat bordered class="q-pa-md">
      <div class="row justify-between items-center q-mb-md">
        <div class="text-subtitle1">{{ $t('reduction_goals') }}</div>
        <q-btn
          color="primary"
          :label="$t('add_goal')"
          icon="add"
          size="sm"
          @click="addGoal"
        />
      </div>

      <div
        v-for="(goal, index) in localGoals"
        :key="index"
        class="row q-gutter-md q-mb-md items-end"
      >
        <div class="col-12 col-md-4">
          <q-input
            v-model.number="goal.reference_year"
            type="number"
            outlined
            :label="$t('reference_year')"
            :rules="[(val) => val > 0 || $t('invalid_year')]"
          />
        </div>
        <div class="col-12 col-md-3">
          <q-input
            v-model.number="goal.target_year"
            type="number"
            outlined
            :label="$t('target_year')"
            :rules="[(val) => val > year || $t('target_year_error')]"
          />
        </div>
        <div class="col-12 col-md-3">
          <q-input
            v-model.number="goal.reduction_percentage"
            type="number"
            outlined
            :label="$t('reduction_percentage')"
            step="0.01"
            min="0"
            max="1"
            :rules="[
              (val) => (val >= 0 && val <= 1) || $t('percentage_error'),
              (val) => !isNaN(val) || $t('invalid_number'),
            ]"
          >
            <template #append>
              <span class="text-caption">%</span>
            </template>
          </q-input>
        </div>
        <div class="col-12 col-md-1">
          <q-btn
            v-if="localGoals.length > 1"
            icon="delete"
            color="negative"
            round
            flat
            size="sm"
            @click="removeGoal(index)"
          />
        </div>
      </div>

      <q-btn
        color="primary"
        :label="$t('save_goals')"
        icon="save"
        @click="saveGoals"
      />
    </q-card>
  </div>
</template>
