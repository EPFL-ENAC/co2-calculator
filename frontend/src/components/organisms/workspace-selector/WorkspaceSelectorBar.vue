<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useWorkspaceStore, unitSlug } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { HOME_ROUTE_NAME } from 'src/router/routeNames';
import { pickDefaultYear } from 'src/router/guards/redirectToDefaultRoute';

const workspaceStore = useWorkspaceStore();
const yearConfigStore = useYearConfigStore();
const router = useRouter();
const route = useRoute();

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
 * Dropdown years = the selected unit's carbon reports intersected with the
 * globally-open years (`startedYears`), so years that have a report but aren't
 * started yet (visible to admins) are hidden. The currently selected year is
 * always re-added so the dropdown still reflects the URL even when it was
 * filtered out. Deduped via the Set and sorted newest-first.
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
    if (year != null) void pushWorkspaceRoute({ year: String(year) });
  },
});

/**
 * Push a workspace route, keeping every current route param and overriding only
 * the ones passed in. A year change overrides just `year` (the unit slug is
 * already in `route.params`); a unit change overrides both `unit` and `year`.
 */
function pushWorkspaceRoute(params: Record<string, string>) {
  return router.push({
    name: HOME_ROUTE_NAME,
    params: { ...route.params, ...params },
  });
}

async function handleUnitChange(unitId: number) {
  if (unitId === selectedUnit.value?.id) return;
  const unit = workspaceStore.units.find((u) => u.id === unitId);
  if (!unit) return;
  await workspaceStore.fetchCarbonReportsForUnit(unitId);
  const year = pickDefaultYear(yearConfigStore.startedYears);
  await pushWorkspaceRoute({ unit: unitSlug(unit), year: String(year) });
}

// Affiliation breadcrumb segments; styling (greyed parents, black leaf) and the
// `›` separators are handled purely in CSS below.
const affiliationSegments = computed(
  () => selectedUnit.value?.affiliations ?? [],
);

async function loadReports(unitId: number | undefined) {
  if (unitId == null) return;
  await workspaceStore.fetchCarbonReportsForUnit(unitId);
}

onMounted(async () => {
  // Each loader handles its own failures internally (and the global http hook
  // toasts the user), so none of these reject — just kick them off in parallel.
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
        <span
          v-if="affiliationSegments.length"
          class="affiliation text-caption"
        >
          <span
            v-for="(segment, index) in affiliationSegments"
            :key="index"
            class="affiliation__segment"
            >{{ segment }}</span
          >
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

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

// Affiliation breadcrumb: parent segments greyed, leaf black, with a `›`
// separator injected before every segment after the first.
.affiliation__segment {
  color: tokens.$color-text-muted;

  &:last-child {
    color: tokens.$color-text;
    font-weight: 500;
  }

  &:not(:first-child)::before {
    content: '›';
    margin: 0 0.25rem;
    color: tokens.$color-text-muted;
  }
}
</style>
