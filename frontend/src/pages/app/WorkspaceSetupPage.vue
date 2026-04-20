<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useTimelineStore, useModuleStore } from 'src/stores/modules';
import type { Unit } from 'src/stores/workspace';
import { useRouter, useRoute } from 'vue-router';
import LabSelectorItem from 'src/components/organisms/workspace-selector/LabSelectorItem.vue';
import YearSelector from 'src/components/organisms/workspace-selector/YearSelector.vue';
import type { YearData } from 'src/components/organisms/workspace-selector/YearSelector.vue';
import type { CarbonReport } from 'src/stores/workspace';
import { MODULE_STATES } from 'src/constant/moduleStates';
import { MODULES_LIST } from 'src/constant/modules';

const workspaceStore = useWorkspaceStore();
const timelineStore = useTimelineStore();
const moduleStore = useModuleStore();
const router = useRouter();
const route = useRoute();

const selectedWorkspace = ref<'calculator' | 'simulator' | null>(null);

// --- COMPUTED ---
const unitsWithRoles = computed(() => workspaceStore.units);

const yearsCount = computed(
  () => workspaceStore.availableCarbonReportYears.length,
);
const hasMultipleYears = computed(
  () => workspaceStore.availableCarbonReportYears.length > 1,
);

const yearRows = computed<YearData[]>(() => {
  const emissionsMap = new Map<number, number>();
  for (const row of moduleStore.state.yearlyValidatedEmissions) {
    const year = row.year;
    const tonnes = row.total_tonnes_co2eq;
    emissionsMap.set(year, tonnes);
  }
  return workspaceStore.availableCarbonReportYears.map((year) => ({
    year,
    tco2eq: emissionsMap.get(year) ?? null,
    status: workspaceStore.carbonReportForYear(year) ? 'complete' : 'missing',
  }));
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

const validatedModulesCount = computed(
  () =>
    Object.values(timelineStore.itemStates).filter(
      (s) => s === MODULE_STATES.Validated,
    ).length,
);

const confirmationReady = computed(() => {
  if (!workspaceStore.selectedUnit || !selectedWorkspace.value) return false;
  if (selectedWorkspace.value === 'simulator') return true;
  return workspaceStore.selectedYear !== null;
});

const simulatorYear = computed(() => {
  const reports = workspaceStore.carbonReports;
  if (reports.length > 0) {
    return reports.reduce((a, b) => (a.year > b.year ? a : b)).year;
  }
  return new Date().getFullYear() - 1;
});

// --- ACTIONS ---

const handleUnitSelect = async (unit: Unit) => {
  workspaceStore.setUnit(unit);
  workspaceStore.setYear(null);
  selectedWorkspace.value = null;
  await Promise.all([
    workspaceStore.fetchCarbonReportsForUnit(unit.id),
    moduleStore.getYearlyValidatedEmissions(unit.id),
  ]);
  // Show real module progress for the most recent report straight away
  const reports = workspaceStore.carbonReports;
  if (reports.length > 0) {
    const mostRecent = reports.reduce((a, b) => (a.year > b.year ? a : b));
    await timelineStore.fetchModuleStates(mostRecent.id);
  }
};

const handleYearSelect = async (year: number) => {
  workspaceStore.setYear(year);
  if (workspaceStore.selectedUnit) {
    const inv: CarbonReport =
      await workspaceStore.selectWithoutFetchingCarbonReportForYear(
        workspaceStore.selectedUnit.id,
        year,
      );
    if (inv?.id) {
      await timelineStore.fetchModuleStates(inv.id);
    }
  }
};

const handleConfirm = () => {
  const unit = workspaceStore.selectedUnit;
  const year = workspaceStore.selectedYear;

  if (unit && year) {
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

const handleConfirmSimulator = () => {
  const unit = workspaceStore.selectedUnit;
  if (unit) {
    router.push({
      name: 'simulation',
      params: {
        ...route.params,
        unit: `${unit.id}-${unit.name.replace(/\s+/g, '-').toLowerCase()}`,
        year: simulatorYear.value,
      },
    });
  }
};

const handleWorkspaceSelect = (workspace: 'calculator' | 'simulator') => {
  selectedWorkspace.value = workspace;
  if (workspace === 'simulator') {
    workspaceStore.setYear(null);
  }
};

const reset = () => {
  workspaceStore.reset();
  timelineStore.reset();
  selectedWorkspace.value = null;
};

onMounted(async () => {
  workspaceStore.reset();
  timelineStore.reset();
  await workspaceStore.getUnits();
});
</script>

<template>
  <q-page class="page-grid">
    <!-- Welcome (only if not ready to confirm) -->
    <q-card flat class="container">
      <h1 class="text-h2 q-mb-xs">{{ $t('workspace_setup_title') }}</h1>
      <p class="text-body1 q-mb-none">
        {{ $t('workspace_setup_description') }}
      </p>
    </q-card>

    <!-- Step 1: Lab Selection — always shown -->
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

    <!-- Step 2: Calculator / Simulator -->
    <q-card v-if="workspaceStore.selectedUnit !== null" flat class="container">
      <h2 class="text-h3 q-mb-xs">
        {{ $t('workspace_setup_workspace_title') }}
      </h2>
      <p class="text-body2 text-secondary q-mb-xl">
        {{ $t('workspace_setup_workspace_description') }}
      </p>

      <div class="row q-gutter-lg">
        <!-- Calculator -->
        <q-card
          flat
          class="col q-pa-none cursor-pointer lab-selector-item"
          :class="{
            'lab-selector-item--selected': selectedWorkspace === 'calculator',
          }"
          :style="{ border: selectedWorkspace === 'calculator' ? '1px solid var(--q-accent)' : '1px solid rgba(0,0,0,0.12)' }"
          @click="handleWorkspaceSelect('calculator')"
        >
          <q-card-section class="q-pb-sm">
            <div class="row items-center q-gutter-sm">
              <q-icon name="o_calculate" size="sm" color="accent" />
              <h3 class="text-h4 text-weight-bold">
                {{ $t('calculator_title') }}
              </h3>
            </div>
            <p class="text-body2 text-secondary q-mt-sm q-mb-none">
              {{ $t('workspace_setup_calculator_description') }}
            </p>
          </q-card-section>
          <q-separator />
          <q-card-section>
            <div class="row items-center justify-between q-mb-xs">
              <span class="text-body2 text-weight-medium">
                {{ $t('workspace_setup_calculator_current_progress') }}
              </span>
              <span class="text-body2 text-weight-medium">
                {{ validatedModulesCount }}/{{ MODULES_LIST.length }}
              </span>
            </div>
            <div class="progress-segments q-my-sm">
              <div
                v-for="i in MODULES_LIST.length"
                :key="i"
                class="segment"
                :class="{
                  filled: i <= validatedModulesCount,
                  selected: selectedWorkspace === 'calculator',
                }"
              ></div>
            </div>
          </q-card-section>
        </q-card>

        <!-- Simulator -->
        <q-card
          flat
          class="col q-pa-none cursor-pointer lab-selector-item"
          :class="{
            'lab-selector-item--selected': selectedWorkspace === 'simulator',
          }"
          :style="{ border: selectedWorkspace === 'simulator' ? '1px solid var(--q-accent)' : '1px solid rgba(0,0,0,0.12)' }"
          @click="handleWorkspaceSelect('simulator')"
        >
          <q-card-section class="q-pb-sm">
            <div class="row items-center q-gutter-sm">
              <q-icon name="o_schema" size="sm" color="accent" />
              <h3 class="text-h4 text-weight-bold">
                {{ $t('workspace_setup_simulator_title') }}
              </h3>
            </div>
            <p class="text-body2 text-secondary q-mt-sm q-mb-none">
              {{ $t('workspace_setup_simulator_description') }}
            </p>
          </q-card-section>
          <q-separator />
          <q-card-section>
            <span class="text-h4 text-weight-bold">3</span>
            <p class="text-body2 text-secondary q-mt-xs q-mb-none">
              {{ $t('workspace_setup_simulator_completed_simulations') }}
            </p>
          </q-card-section>
        </q-card>
      </div>
    </q-card>

    <!-- Step 3: Year Selection — calculator path only -->
    <q-card v-if="selectedWorkspace === 'calculator'" flat class="container">
      <h2 class="text-h3 q-mb-xs">{{ $t('workspace_setup_year_title') }}</h2>
      <p class="text-body2 text-secondary q-mb-xl">
        {{ $t('workspace_setup_year_description') }}
      </p>
      <span class="text-h5 text-weight-medium">{{
        $t('workspace_setup_year_counter', {
          count: yearsCount,
        })
      }}</span>
      <div v-if="workspaceStore.carbonReportsError" class="q-mt-sm">
        <q-banner class="container text-negative border-negative q-pa-lg">
          <template #avatar>
            <q-icon name="o_warning" color="grey-3" size="md" />
          </template>
          <p class="text-body2 text-weight-bold q-mt-sm">
            {{ workspaceStore.carbonReportsError.message }}
          </p>
        </q-banner>
      </div>
      <YearSelector
        v-else
        class="q-mt-md"
        :selected-year="workspaceStore.selectedYear"
        :years="yearRows"
        @select="handleYearSelect"
      />
    </q-card>

    <!-- Step 4: Confirmation -->
    <q-card v-if="confirmationReady" flat class="container q-gutter-lg">
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
          v-if="hasMultipleYears && workspaceStore.selectedYear"
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
          v-if="workspaceSelected && selectedWorkspace === 'calculator'"
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
        <q-btn
          v-if="selectedWorkspace === 'simulator'"
          color="accent"
          :label="$t('workspace_setup_continue_simulator')"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          @click="handleConfirmSimulator"
        />
      </div>
    </q-card>
  </q-page>
</template>
