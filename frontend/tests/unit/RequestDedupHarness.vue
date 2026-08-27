<template>
  <div data-testid="result">{{ result }}</div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useModuleStore } from '@/stores/modules';
import { useWorkspaceStore } from '@/stores/workspace';
import { useFactorsStore } from '@/stores/factors';
import { getHeadcountMembers } from '@/api/modules';
import { CARBON_PROJECT } from '@/constant/carbon-project';
import { MODULES } from '@/constant/modules';

// Test-only driver for the request-dedup regression tests (#2360): runs one
// scenario against the real store/api layer and renders the outcome, so the
// spec can assert on rendered text while counting intercepted requests.
const props = defineProps<{
  scenario:
    | 'resolve-concurrent'
    | 'resolve-retry'
    | 'members-dedup'
    | 'explore-seed-cache'
    | 'class-options-concurrent'
    | 'class-options-retry'
    | 'labelled-options-concurrent'
    | 'subclass-options'
    | 'class-nodes-concurrent';
}>();

const result = ref('pending');
const moduleStore = useModuleStore();
const workspaceStore = useWorkspaceStore();
const factorsStore = useFactorsStore();

const resolveOnce = () =>
  moduleStore.resolveCarbonReportId(7, 2024, CARBON_PROJECT.calculator);
const classOptionsOnce = () =>
  factorsStore.fetchClassOptions(MODULES.ProfessionalTravel, 'plane', 2024);
const labelledOptionsOnce = () =>
  factorsStore.fetchClassOptions(
    MODULES.ProfessionalTravel,
    'plane',
    2024,
    true,
  );
const subclassOptionsOnce = () =>
  factorsStore.fetchSubclassOptions(
    MODULES.ProfessionalTravel,
    'plane',
    'Boeing',
    2024,
  );
// Same shape the planner rows component calls (#2391): the submodule key,
// not the numeric factor id.
const classNodesOnce = () =>
  factorsStore.fetchClassNodes(
    MODULES.ResearchFacilities,
    'research-facilities',
    2024,
  );

async function run(): Promise<string> {
  if (props.scenario === 'resolve-concurrent') {
    const ids = await Promise.all([1, 2, 3, 4, 5].map(() => resolveOnce()));
    return `ids:${ids.join(',')}`;
  }
  if (props.scenario === 'resolve-retry') {
    try {
      await resolveOnce();
      return 'unexpected-success';
    } catch {
      // Expected: the first lookup fails; a rejection must not be cached.
    }
    return `retried:${await resolveOnce()}`;
  }
  if (props.scenario === 'class-options-concurrent') {
    const maps = await Promise.all(
      [1, 2, 3, 4, 5].map(() => classOptionsOnce()),
    );
    return `classes:${maps.map((m) => m.length).join(',')}`;
  }
  if (props.scenario === 'class-options-retry') {
    try {
      await classOptionsOnce();
      return 'unexpected-success';
    } catch {
      // Expected: the first lookup fails; a rejection must not be cached.
    }
    const retried = await classOptionsOnce();
    return `retried:${retried.length}`;
  }
  if (props.scenario === 'labelled-options-concurrent') {
    const opts = await Promise.all(
      [1, 2, 3, 4, 5].map(() => labelledOptionsOnce()),
    );
    return `options:${opts.map((o) => o.length).join(',')}`;
  }
  if (props.scenario === 'subclass-options') {
    const subs = await subclassOptionsOnce();
    return `subclasses:${subs.map((o) => o.value).join('|')}`;
  }
  if (props.scenario === 'class-nodes-concurrent') {
    const lists = await Promise.all(
      [1, 2, 3, 4, 5].map(() => classNodesOnce()),
    );
    return `rows:${lists.map((l) => l.length).join(',')}`;
  }
  if (props.scenario === 'members-dedup') {
    const bursts = await Promise.all(
      [1, 2, 3].map(() => getHeadcountMembers(9)),
    );
    // A later call must refetch: only in-flight promises are shared, results
    // are never cached (roster edits must stay visible).
    const followUp = await getHeadcountMembers(9);
    return `members:${bursts.map((m) => m.length).join(',')};followup:${followUp.length}`;
  }
  // The explore page resolves its report once via the workspace store; that
  // resolution must seed the module store so this resolveCarbonReportId call
  // hits cache instead of re-issuing the same lookup (#2360 follow-up).
  const seeded = await workspaceStore.selectSimulatorExploreCarbonReport(
    7,
    2024,
  );
  const resolved = await moduleStore.resolveCarbonReportId(
    7,
    2024,
    CARBON_PROJECT.explorer,
  );
  return `seeded:${seeded.id},resolved:${resolved}`;
}

run()
  .then((outcome) => {
    result.value = outcome;
  })
  .catch((e: unknown) => {
    result.value = e instanceof Error ? `error:${e.message}` : 'error';
  });
</script>
