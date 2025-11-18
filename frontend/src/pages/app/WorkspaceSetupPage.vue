<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useRouter, useRoute } from 'vue-router';
import LabSelectorItem from 'src/components/organisms/workspace-selector/LabSelectorItem.vue';
import YearSelector from 'src/components/organisms/workspace-selector/YearSelector.vue';

const selectedLab = ref<number | null>(null);
const selectedYear = ref<number | null>(null);
const workspaceStore = useWorkspaceStore();
const router = useRouter();
const route = useRoute();

// Units come from backend with roles already attached, filtered, and sorted
const unitsWithRoles = computed(() => workspaceStore.units);

// Only show year selection if there are multiple years for the current unit or if there's an error
const showYearSelection = computed(() => {
  const yearsCount = workspaceStore.unitResults?.years.length ?? 0;
  const hasUnitSelected =
    unitsWithRoles.value.length === 1 || selectedLab.value !== null;
  return (
    hasUnitSelected &&
    (workspaceStore.unitResultsError !== null || yearsCount > 1)
  );
});

// Show confirmation if unit and year are selected
const showConfirmation = computed(() => {
  return (
    (selectedLab.value !== null || unitsWithRoles.value.length === 1) &&
    (selectedYear.value !== null ||
      workspaceStore.unitResults?.years.length === 1)
  );
});

// Confirm selection and navigate to home
const confirmSelection = () => {
  const language = route.params.language || 'en';
  workspaceStore.setUnit(currentUnit.value!);
  workspaceStore.setYear(selectedYear.value!);

  router.push({
    name: 'home',
    params: {
      language,
      unit: encodeURIComponent(currentUnit.value.name),
      year: selectedYear.value,
    },
  });
};

// Reset selections
const reset = () => {
  selectedLab.value = null;
  selectedYear.value = null;
};

// If only one lab, auto-select it
watch(
  unitsWithRoles,
  (units) => {
    if (units.length === 1 && !selectedLab.value) {
      selectedLab.value = units[0].id;
    }
  },
  { immediate: true },
);

const currentUnit = computed(() => {
  if (unitsWithRoles.value.length === 1) {
    return unitsWithRoles.value[0];
  }
  return selectedLab.value
    ? unitsWithRoles.value.find((u) => u.id === selectedLab.value)
    : null;
});

// If unit has only one year, auto-select it
watch(currentUnit, async (unit) => {
  if (unit) {
    await workspaceStore.fetchUnitResults(currentUnit.value.id);

    if (workspaceStore.unitResults?.years.length === 1) {
      selectedYear.value = workspaceStore.unitResults.years[0].year;
    }
  }
});

// Initial unit data fetch
onMounted(async () => {
  await workspaceStore.fetchUnits();

  if (unitsWithRoles.value.length === 1) {
    selectedLab.value = unitsWithRoles.value[0].id;
    await workspaceStore.fetchUnitResults(currentUnit.value.id);
  }
});
</script>

<template>
  <q-page class="layout-grid">
    <!-- Welcome (only if workspace not fully selected) -->
    <q-card
      v-if="!workspaceStore.selectedUnit || !workspaceStore.selectedYear"
      flat
      class="container"
    >
      <h1 class="text-h2 q-mb-xs">{{ $t('workspace_setup_title') }}</h1>
      <p class="text-body1 q-mb-none">
        {{ $t('workspace_setup_description') }}
      </p>
    </q-card>

    <!-- Lab Selection -->
    <q-card
      v-if="workspaceStore.unitsError || unitsWithRoles.length > 1"
      flat
      class="container"
    >
      <h2 class="text-h3 q-mb-xs">{{ $t('workspace_setup_unit_title') }}</h2>
      <p class="text-body2 text-secondary q-mb-xl">
        {{ $t('workspace_setup_unit_description') }}
      </p>
      <span class="text-h5 text-weight-medium">{{
        $t('workspace_setup_unit_counter', {
          count: unitsWithRoles.length,
        })
      }}</span>
      <div v-if="workspaceStore.unitsError" class="q-mt-sm">
        <q-banner class="container text-negative border-negative q-pa-lg">
          <template v-slot:avatar>
            <q-icon name="o_warning" color="grey-3" size="md" />
          </template>
          <p class="text-body2 text-weight-bold q-mt-sm">
            {{ $t('workspace_setup_unit_error') }}
          </p>
        </q-banner>
      </div>
      <div v-else class="q-mt-sm column-grid-2">
        <LabSelectorItem
          v-for="unit in unitsWithRoles"
          :key="unit.id"
          :selected="selectedLab === unit.id"
          :unit="unit"
          @click="selectedLab = unit.id"
        />
      </div>
    </q-card>

    <!-- Year Selection -->
    <q-card v-if="showYearSelection" flat class="container">
      <h2 class="text-h3 q-mb-xs">{{ $t('workspace_setup_year_title') }}</h2>
      <p class="text-body2 text-secondary q-mb-xl">
        {{ $t('workspace_setup_year_description') }}
      </p>
      <span class="text-h5 text-weight-medium">{{
        $t('workspace_setup_year_counter', {
          count: workspaceStore.unitResults?.years.length ?? 0,
        })
      }}</span>
      <div v-if="workspaceStore.unitResultsError" class="q-mt-sm">
        <q-banner class="container text-negative border-negative q-pa-lg">
          <template v-slot:avatar>
            <q-icon name="o_warning" color="grey-3" size="md" />
          </template>
          <p class="text-body2 text-weight-bold q-mt-sm">
            {{ $t('workspace_setup_year_error') }}
          </p>
        </q-banner>
      </div>
      <YearSelector
        v-else-if="workspaceStore.unitResults"
        class="q-mt-md"
        :selected-year="selectedYear"
        :years="
          workspaceStore.unitResults.years.map((y) => ({
            year: y.year,
            progress: 100,
            completed_modules: y.completed_modules,
            comparison: y.last_year_comparison ?? null,
            kgco2: y.kgco2,
            status: 'complete',
          }))
        "
        @select="selectedYear = $event"
      />
    </q-card>

    <!-- Confirmation -->
    <q-card v-if="showConfirmation" flat class="container q-gutter-lg">
      <h2 class="text-h3 q-ml-none q-mb-lg">
        {{ $t('workspace_setup_confirm_selection') }}
      </h2>
      <div class="column-grid-2">
        <q-card flat v-if="unitsWithRoles.length > 1" class="container">
          <h6 class="text-h6 text-weight-medium">
            {{ $t('workspace_setup_confirm_lab') }}
          </h6>
          <h3 class="text-h3 text-weight-medium q-pt-sm">
            {{ currentUnit?.name }}
          </h3>
          <p class="text-caption">
            {{ currentUnit?.affiliations.join(' / ') }}
          </p>
        </q-card>
        <q-card
          flat
          v-if="(workspaceStore.unitResults?.years.length ?? 0) > 1"
          class="container q-mt-md"
          style="flex: 2 1 0"
        >
          <h6 class="text-h6 text-weight-medium">
            {{ $t('workspace_setup_confirm_year') }}
          </h6>
          <h3 class="text-h3 text-weight-medium q-pt-sm">
            {{ selectedYear }}
          </h3>
        </q-card>
      </div>
      <div class="row q-gutter-sm q-mt-lg justify-end">
        <q-btn
          color="grey-4"
          text-color="primary"
          :label="$t('workspace_setup_restart')"
          unelevated
          no-caps
          outline
          size="md"
          class="text-weight-medium"
          @click="reset"
        />
        <q-btn
          color="accent"
          :label="$t('workspace_setup_confirm_selection')"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          @click="confirmSelection"
        />
      </div>
    </q-card>
  </q-page>
</template>
