<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import type { Unit } from 'src/stores/workspace';
import { HOME_ROUTE_NAME } from 'src/router/routeNames';

const workspaceStore = useWorkspaceStore();
const yearConfigStore = useYearConfigStore();
const router = useRouter();
const route = useRoute();

/** Build the `id-slugified-name` unit route param (same format as the guards). */
function unitSlug(unit: Unit): string {
  return `${unit.id}-${unit.name.replace(/\s+/g, '-').toLowerCase()}`;
}

const selectedUnit = computed(() => workspaceStore.selectedUnit);

const unitOptions = computed(() =>
  workspaceStore.units.map((unit) => ({ label: unit.name, value: unit.id })),
);

const selectedUnitId = computed({
  get: () => selectedUnit.value?.id ?? null,
  set: (id: number | null) => {
    if (id != null) void handleUnitChange(id);
  },
});

/**
 * Years that are globally open (`is_started`) AND have a carbon report for the
 * selected unit. Mirrors the intersection used by the old workspace-setup page.
 * The currently selected year is always included so the dropdown reflects the URL.
 */
const yearOptions = computed<number[]>(() => {
  const started = yearConfigStore.startedYears;
  const years = new Set(
    workspaceStore.carbonReports
      .filter((report) => started.has(report.year))
      .map((report) => report.year),
  );
  if (workspaceStore.selectedYear != null) {
    years.add(workspaceStore.selectedYear);
  }
  return [...years].sort((a, b) => b - a);
});

const selectedYear = computed({
  get: () => workspaceStore.selectedYear,
  set: (year: number | null) => {
    if (year != null) void handleYearChange(year);
  },
});

/**
 * Pick the most recent open year for the freshly-loaded reports of a unit.
 * Falls back to the latest report year, then to last calendar year.
 */
function defaultYear(): number {
  const started = yearConfigStore.startedYears;
  const reportYears = workspaceStore.carbonReports.map((report) => report.year);
  const openYears = reportYears.filter((year) => started.has(year));
  if (openYears.length > 0) return Math.max(...openYears);
  if (reportYears.length > 0) return Math.max(...reportYears);
  return new Date().getFullYear() - 1;
}

async function handleUnitChange(unitId: number) {
  if (unitId === selectedUnit.value?.id) return;
  const unit = workspaceStore.units.find((u) => u.id === unitId);
  if (!unit) return;
  await workspaceStore.fetchCarbonReportsForUnit(unitId);
  const year = defaultYear();
  await router.push({
    name: HOME_ROUTE_NAME,
    params: { ...route.params, unit: unitSlug(unit), year: String(year) },
  });
}

async function handleYearChange(year: number) {
  if (year === workspaceStore.selectedYear) return;
  const unit = selectedUnit.value;
  if (!unit) return;
  await router.push({
    name: HOME_ROUTE_NAME,
    params: { ...route.params, unit: unitSlug(unit), year: String(year) },
  });
}

const affiliationSegments = computed(
  () => selectedUnit.value?.affiliations ?? [],
);
// Parent path (greyed), with trailing separator when there's a leaf after it.
const affiliationPrefix = computed(() => {
  const segments = affiliationSegments.value;
  return segments.length > 1 ? `${segments.slice(0, -1).join(' › ')} › ` : '';
});
// Leaf affiliation, shown in black.
const affiliationLeaf = computed(() => affiliationSegments.value.at(-1) ?? '');

async function loadReports(unitId: number | undefined) {
  if (unitId == null) return;
  await workspaceStore.fetchCarbonReportsForUnit(unitId);
}

onMounted(async () => {
  await Promise.all([
    workspaceStore.units.length === 0
      ? workspaceStore.getUnits()
      : Promise.resolve(),
    yearConfigStore.fetchConfiguredYears(),
    loadReports(selectedUnit.value?.id),
  ]);
});

// Keep the year dropdown options in sync when the unit changes via the URL.
watch(
  () => selectedUnit.value?.id,
  (unitId) => void loadReports(unitId),
);
</script>

<template>
  <div class="workspace-selector-bar">
    <div class="row items-center justify-between no-wrap q-col-gutter-lg">
      <div class="row items-end no-wrap q-gutter-lg">
        <div class="workspace-selector-bar__field">
          <span class="text-caption text-secondary text-weight-medium">
            {{ $t('workspace_unit_label') }}
          </span>
          <q-select
            v-model="selectedUnitId"
            :options="unitOptions"
            emit-value
            map-options
            dense
            outlined
            options-dense
            class="workspace-selector-bar__select"
          />
        </div>
        <div class="workspace-selector-bar__field">
          <span class="text-caption text-secondary text-weight-medium">
            {{ $t('workspace_year_label') }}
          </span>
          <q-select
            v-model="selectedYear"
            :options="yearOptions"
            dense
            outlined
            options-dense
            class="workspace-selector-bar__select"
          />
        </div>
      </div>

      <div
        v-if="selectedUnit"
        class="column items-end text-right workspace-selector-bar__user"
      >
        <span class="text-body2">
          {{ selectedUnit.principal_user_name
          }}<template v-if="selectedUnit.current_user_role"
            >,
            <span class="text-info text-weight-medium">{{
              $t(selectedUnit.current_user_role)
            }}</span></template
          >
        </span>
        <span v-if="affiliationLeaf" class="text-caption">
          <span class="text-secondary">{{ affiliationPrefix }}</span
          ><span class="text-black text-weight-medium">{{ affiliationLeaf }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.workspace-selector-bar {
  &__field {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  &__select {
    min-width: 200px;
  }

  &__user {
    min-width: 0;
  }
}
</style>
