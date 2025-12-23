<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import type { Unit } from 'src/stores/workspace';
import { useRouter, useRoute } from 'vue-router';
import LabSelectorItem from 'src/components/organisms/workspace-selector/LabSelectorItem.vue';
import YearSelector from 'src/components/organisms/workspace-selector/YearSelector.vue';

const workspaceStore = useWorkspaceStore();
const router = useRouter();
const route = useRoute();

// --- COMPUTED ---
const unitsWithRoles = computed(() => workspaceStore.units);

const workspaceNotSelected = computed(() => {
  return (
    workspaceStore.selectedUnit === null || workspaceStore.selectedYear === null
  );
});

const showYearSelection = computed(() => {
  return (
    workspaceStore.selectedUnit !== null &&
    (workspaceStore.unitResults?.years.length ?? 0) > 1
  );
});

const yearsCount = computed(() => {
  return workspaceStore.unitResults?.years.length ?? 0;
});

const hasMultipleYears = computed(() => {
  return (workspaceStore.unitResults?.years.length ?? 0) > 1;
});

const selectedUnitAffiliations = computed(() => {
  const unit = workspaceStore.selectedUnit;
  if (!unit) return '';
  return unit.affiliations.join(', ');
});

const workspaceSelected = computed(() => {
  return routeUnitParam.value !== null && workspaceStore.selectedYear !== null;
});

const routeUnitParam = computed(
  () =>
    `${workspaceStore.selectedUnit?.id}-${workspaceStore.selectedUnit?.name.replace(/\s+/g, '-').toLowerCase()}`,
);

// --- ACTIONS ---

const handleUnitSelect = async (unit: Unit) => {
  // 1. Set the unit in Pinia
  workspaceStore.setUnit(unit);
  workspaceStore.setYear(null); // Reset year in store

  // 2. Fetch years available for this specific unit
  await workspaceStore.getUnitResults(unit.id);

  // 3. Auto-select year if only one exists
  if (workspaceStore.unitResults?.years.length === 1) {
    workspaceStore.setYear(workspaceStore.unitResults.years[0].year);
  }
};

const handleYearSelect = (year: number) => {
  workspaceStore.setYear(year);
};

const handleConfirm = () => {
  const unit = workspaceStore.selectedUnit;
  const year = workspaceStore.selectedYear;

  if (unit && year) {
    // Navigate to the dashboard with the clean URL structure
    // We slugify the name for the URL: ID-NAME
    router.push({
      name: 'workspace-dashboard',
      params: {
        ...route.params,
        unit: `${unit.id}-${unit.name.replace(/\s+/g, '-').toLowerCase()}`,
        year: year,
      },
    });
  }
};

const reset = () => {
  workspaceStore.reset();
};

onMounted(async () => {
  // Clear any old selection leftovers when entering setup
  workspaceStore.reset();
  await workspaceStore.getUnits();
});
</script>

<template>
  <q-page class="page-grid">
    <!-- Welcome (only if workspace not fully selected) -->
    <q-card v-if="workspaceNotSelected" flat class="container">
      <h1 class="text-h2 q-mb-xs">{{ $t('workspace_setup_title') }}</h1>
      <p class="text-body1 q-mb-none">
        {{ $t('workspace_setup_description') }}
      </p>
    </q-card>

    <!-- Lab Selection -->
    <q-card flat class="container">
      <h2 class="text-h3 q-mb-xs">{{ $t('workspace_setup_unit_title') }}</h2>
      <p class="text-body2 text-secondary q-mb-xl">
        {{ $t('workspace_setup_unit_description') }}
      </p>
      <span class="text-h5 text-weight-medium">{{
        $t('workspace_setup_unit_counter', {
          count: unitsWithRoles.length,
        })
      }}</span>
      <div v-if="workspaceStore.unitsErrors.length > 0" class="q-mt-sm">
        <q-banner class="container text-negative border-negative q-pa-lg">
          <template #avatar>
            <q-icon name="o_warning" color="grey-3" size="md" />
          </template>
          <p class="text-body2 text-weight-bold q-mt-sm">
            {{ workspaceStore.unitsErrors[0]?.message }}
          </p>
        </q-banner>
      </div>
      <div v-else class="q-mt-sm grid-2-col">
        <LabSelectorItem
          v-for="unit in unitsWithRoles"
          :key="unit.id"
          :selected="workspaceStore.selectedUnit?.id === unit.id"
          :unit="unit"
          @click="handleUnitSelect(unit)"
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
          count: yearsCount,
        })
      }}</span>
      <div v-if="workspaceStore.unitResultsErrors.length > 0" class="q-mt-sm">
        <q-banner class="container text-negative border-negative q-pa-lg">
          <template #avatar>
            <q-icon name="o_warning" color="grey-3" size="md" />
          </template>
          <p class="text-body2 text-weight-bold q-mt-sm">
            {{ workspaceStore.unitResultsErrors[0]?.message }}
          </p>
        </q-banner>
      </div>
      <YearSelector
        v-else-if="workspaceStore.unitResults"
        class="q-mt-md"
        :selected-year="workspaceStore.selectedYear"
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
        @select="handleYearSelect"
      />
    </q-card>

    <!-- Confirmation -->
    <q-card v-if="!workspaceNotSelected" flat class="container q-gutter-lg">
      <h2 class="text-h3 q-ml-none q-mb-lg">
        {{ $t('workspace_setup_confirm_selection') }}
      </h2>
      <div class="grid-2-col">
        <q-card v-if="unitsWithRoles.length > 1" flat class="container">
          <h6 class="text-h6 text-weight-medium">
            {{ $t('workspace_setup_confirm_lab') }}
          </h6>
          <h3 class="text-h3 text-weight-medium q-pt-sm">
            {{ workspaceStore.selectedUnit?.name }}
          </h3>
          <p class="text-caption">
            {{ selectedUnitAffiliations }}
          </p>
        </q-card>
        <q-card
          v-if="hasMultipleYears"
          flat
          class="container q-mt-md"
          style="flex: 2 1 0"
        >
          <h6 class="text-h6 text-weight-medium">
            {{ $t('workspace_setup_confirm_year') }}
          </h6>
          <h3 class="text-h3 text-weight-medium q-pt-sm">
            {{ workspaceStore.selectedYear }}
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
          v-if="workspaceSelected"
          color="accent"
          :label="$t('workspace_setup_confirm_selection')"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          :to="{
            name: 'home',
            params: {
              ...route.params,
              unit: routeUnitParam,
              year: workspaceStore.selectedYear,
            },
          }"
          @click="handleConfirm"
        />
      </div>
    </q-card>
  </q-page>
</template>
