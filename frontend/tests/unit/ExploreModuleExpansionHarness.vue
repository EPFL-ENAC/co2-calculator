<template>
  <ExploreModuleExpansionList
    :modules="modules"
    :unit-id="7"
    :year="2024"
    :carbon-report-id="42"
  />
</template>

<script setup lang="ts">
// Test-only driver for the explore-module-expansion regression tests
// (#2360). Real module configs, no submodules mounted for Equipment/Purchase:
// SubModuleSection's deep tree (ModuleTable/ModuleForm) needs its own q-*
// component registrations this bare CT Vite instance doesn't provide (see
// playwright/index.ts) — count-fetch deferral is ExploreModuleExpansionList's
// own concern and is fully exercised without it. ResearchFacilities needs no
// such registrations: PlannerResearchFacilityRows fetches from its own
// `onMounted`, which Vue runs even when its q-* descendants render inert —
// it's also the exact GlitchTip 312 lookup (now
// `taxonomies/module/research-facilities/...?year=...`), so it
// proves the content-mount gate for real. Building this data here, inside a
// .vue file, keeps `@/...`-aliased imports out of the spec file, which
// Playwright's Node-side test loader cannot resolve (only the Vite bundle
// used for mounting knows that alias).
import ExploreModuleExpansionList from '@/components/organisms/module/ExploreModuleExpansionList.vue';
import { MODULES } from '@/constant/modules';
import {
  equipment,
  purchase,
  researchFacilities,
} from '@/constant/module-config';
import type { ExploreModule } from '@/utils/exploreModules';

const modules: ExploreModule[] = [
  { type: MODULES.Equipment, config: equipment, submodules: [] },
  { type: MODULES.Purchase, config: purchase, submodules: [] },
  {
    type: MODULES.ResearchFacilities,
    config: researchFacilities,
    submodules: [],
  },
];
</script>
