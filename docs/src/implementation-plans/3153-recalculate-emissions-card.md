---
status: delivered
issue: 3153
last_updated: 2026-10-29
summary: "Add a Recalculate emissions card to the pipeline operations console (module, optional data entry type, year, confirm), open both POST /sync/recalculate-emissions endpoints to backoffice.pipeline_operations edit as well as backoffice.configuration edit, and delete the dead per-type recalculate emit chain left behind when #780 removed its button."
---

# Recalculate emissions card on the pipeline console (#3153)

## Problem

#780 removed the per-type "Recalculate" button, so the backoffice had no
UI left to trigger an emission recalculation. #3142 had to call
`POST /sync/recalculate-emissions/{module}` from the browser console. The
endpoints and the store actions wrapping them were still there. So was a
`recalculate` emit chain that nothing ever fired: `UploadCard` →
`UploadCardData` / `UploadCardFactors` → `SubmoduleItem` /
`ModuleUploadsSection` → `triggerTypeRecalculation`, injected from
`ModuleConfig`.

## What shipped

- **Backend gate.** `can_recalculate_emissions` /
  `require_pipeline_ops_or_config_edit` in `app/utils/scoping.py` mirror
  `can_view_module_flow` / `require_module_or_config_view`. They admit
  `backoffice.pipeline_operations` edit OR `backoffice.configuration` edit,
  and any other user gets 403. Both recalculate endpoints in
  `app/api/v1/data_sync.py` use it. Both keys are bare and super-admin-only
  (`app/models/user.py`), so the pure `has_permission` check agrees with OPA.
- **Card.** `RecalculateEmissionsCard.vue` sits next to
  `RecomputeStatsCard` on `PipelineOperationsConsolePage`. It shows only
  when the user holds either edit key, checked through
  `authStore.hasUserPermission`. The user picks a module, an optional data
  entry type (options from `MODULE_SUBMODULES`), and a configured year. The
  confirm dialog reuses the `data_management_recalculate_emissions_*`
  overwrite warning.
  - With a data entry type, the card calls `initiateEmissionRecalculation`.
  - Without one, it calls `initiateModuleEmissionRecalculation(…, false)`.
    The module path passes `only_stale=false` because an operator asking
    for a recalc wants a full one.
  - The card emits `triggered` and the page refetches its pipeline list.
    The new pipeline row then streams live, so the user can follow the job.
- **Deleted.** The `recalculate` emit, the
  `hasRecalcButton`/`recalcStatus`/`recalcRunning` props,
  `triggerTypeRecalculation`, `recalcTypeRunning`, the
  `getRecalcStatus` / `recalcTypeRunning` / `triggerTypeRecalculation`
  provides, and `yearConfig.getRecalcStatus`. The module-level
  `ModuleRecalculationDialog` and the "recalculation needed" badge stay.
- **Tests.**
  - `backend/tests/unit/utils/test_recalc_emissions_gate.py` covers each
    edit key passing, and 403 for no permissions, view-only, and a
    scoped `backoffice.configuration/<cf>` edit grant. Denials log the
    same `Permission check denied` line as `require_permission`.
  - `frontend/tests/unit/recalculate-emissions-card.spec.ts` checks the
    per-type POST and the module POST with `only_stale=false`.
