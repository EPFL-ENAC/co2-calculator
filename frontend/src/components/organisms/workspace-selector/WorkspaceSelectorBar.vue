<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useWorkspaceStore, unitSlug } from 'src/stores/workspace';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { useAuthStore } from 'src/stores/auth';
import { ROLES } from 'src/constant/roles';
import { HOME_ROUTE_NAME } from 'src/router/routeNames';
import { pickDefaultYear } from 'src/router/guards/redirectToDefaultRoute';
import { resolveNoWorkspaceRoute } from 'src/utils/unauthorized';

const workspaceStore = useWorkspaceStore();
const yearConfigStore = useYearConfigStore();
const authStore = useAuthStore();
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
 * Dropdown years = the globally-open years (`startedYears`, hydrated from the
 * session bootstrap). Selecting a year the unit has no report for is fine — the
 * workspace-home endpoint get-or-creates the report server-side. The currently
 * selected year is always re-added so the dropdown still reflects the URL even
 * when it isn't (or no longer is) started. Deduped and sorted newest-first.
 */
const yearOptions = computed<number[]>(() => {
  const years = new Set(yearConfigStore.startedYears);
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

// Both dropdowns are driven entirely by store state hydrated elsewhere: units
// and started years come from the session bootstrap, and navigating (unit or
// year change) re-runs the workspace guard's single aggregate call. No fetches
// are needed here.
async function handleUnitChange(unitId: number) {
  if (unitId === selectedUnit.value?.id) return;
  const unit = workspaceStore.units.find((u) => u.id === unitId);
  if (!unit) return;
  // `pickDefaultYear` requires a non-empty set — if every globally-open year
  // closed while this tab stayed open, there's no default year to switch to.
  if (yearConfigStore.startedYears.size === 0) {
    await router.push(resolveNoWorkspaceRoute('no-open-year'));
    return;
  }
  const year = pickDefaultYear(yearConfigStore.startedYears);
  await pushWorkspaceRoute({ unit: unitSlug(unit), year: String(year) });
}

// Affiliation breadcrumb segments; styling (greyed parents, black leaf) and the
// `›` separators are handled purely in CSS below.
const affiliationSegments = computed(
  () => selectedUnit.value?.affiliations ?? [],
);

const isPrincipalUser = computed(
  () => selectedUnit.value?.current_user_role === ROLES.PrincipalUser,
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
          <!-- testid on this wrapper, not q-select: Quasar 2.25 also forwards
               it onto the internal focus-target input, doubling matches. -->
          <div data-testid="workspace-unit-select">
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
        </div>
        <div class="workspace-selector-bar__field">
          <span class="text-caption text-secondary text-weight-medium">
            {{ $t('workspace_year_label') }}
          </span>
          <div data-testid="workspace-year-select">
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
      </div>

      <div
        v-if="selectedUnit"
        class="column items-end text-right workspace-selector-bar__user"
      >
        <span class="text-body2">
          <span class="workspace-selector-bar__name">{{
            authStore.displayName
          }}</span
          ><template v-if="selectedUnit.current_user_role"
            >,
            <span class="text-info text-weight-medium">{{
              $t(selectedUnit.current_user_role)
            }}</span></template
          >
        </span>
        <span
          v-if="!isPrincipalUser && selectedUnit.principal_user_name"
          class="row items-baseline no-wrap text-body2 workspace-selector-bar__principal"
        >
          <span class="text-secondary">{{
            $t('workspace_unit_manager_label')
          }}</span>
          <a
            v-if="selectedUnit.principal_user_email"
            :href="`mailto:${selectedUnit.principal_user_email}`"
            class="workspace-selector-bar__principal-link"
            >{{ selectedUnit.principal_user_name }}</a
          >
          <span v-else>{{ selectedUnit.principal_user_name }}</span>
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
@use '@/css/02-tokens' as tokens;

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
    row-gap: 0.125rem;
  }

  &__name {
    font-weight: tokens.$text-weight-medium;
  }

  &__principal {
    column-gap: tokens.$spacing-xs;
  }

  &__principal-link {
    color: tokens.$link-color;
    text-decoration: underline;
    text-decoration-color: tokens.$link-underline-color;
    text-underline-offset: tokens.$link-underline-offset;
    transition:
      color tokens.$transition-default,
      text-decoration-color tokens.$transition-default;

    &:hover {
      color: tokens.$link-hover-color;
      text-decoration-color: tokens.$link-hover-underline-color;
    }
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
