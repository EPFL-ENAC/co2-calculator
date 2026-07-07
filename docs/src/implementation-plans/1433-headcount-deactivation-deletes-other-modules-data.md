---
status: proposed
issue: 1433
last_updated: 2026-07-07
title: "Headcount module deactivation hides unrelated module data in backoffice Configurator"
summary: "Deactivating Headcount in the Year Configuration cascades to hide Equipment/Process Emissions/Purchases data, but the exact mechanism was not located by static code review; plan starts with pinning it down, then applies the appropriate fix."
---

# Headcount module deactivation hides unrelated module data in backoffice Configurator

## Problem

Reported in EPFL-ENAC/co2-calculator#1433: in the backoffice Configurator (Year
Configuration screen), populating Headcount, Professional Travel, Equipment,
and Process Emissions with data, then deactivating the **Headcount** module,
causes data in unrelated modules (Equipment, Process Emissions, Purchases) to
appear deleted/hidden. The reporter accepts the coupling to Professional
Travel (genuinely people-linked) but not to Equipment/Process
Emissions/Purchases.

## Design

**What was confirmed by code review** (backend + frontend), and what was
ruled out as the cause:

- The "enabled" toggle is `YearConfiguration.config["modules"][<module_type_id>]["enabled"]`,
  a JSON blob on the year-configuration row (`backend/app/schemas/year_configuration.py`,
  `ModuleConfig.enabled`). Flipping it goes:
  `useModuleConfig.updateModuleEnabled` (frontend/src/composables/useModuleConfig.ts:122)
  → `yearConfigStore.updateConfig()` → `PATCH` handled by
  `update_year_configuration` (backend/app/api/v1/year_configuration.py:781),
  which merges the patch via `_deep_merge()` (same file, line 333).
  `_deep_merge` only recurses into keys present in **both** base and patch
  dicts — sibling module keys (Equipment=4, Purchase=5, ProcessEmissions=8)
  are untouched by a patch that only contains `modules["1"]`. **Ruled out**:
  this merge does not clobber other modules' config.
- Frontend visibility/enabled getters (`isModuleEnabled`, `isModuleVisible`,
  `getModule`, `visibleModules` in `frontend/src/stores/yearConfig.ts:406-484`)
  are all keyed by each module's own `moduleTypeId`, independently. No shared
  or global flag was found that one module's `enabled` state feeds into.
  **Ruled out**: no cross-module read of Headcount's flag in these getters.
- No FK or cascade-delete (`ondelete=CASCADE` or ORM `cascade=`) was found
  linking `DataEntry`/`CarbonReportModule` rows across modules, and nothing
  in `carbon_report_module_service.py` / `carbon_report_service.py`
  conditions on Headcount's enabled state. Deactivating a module only writes
  to the `YearConfiguration.config` JSON — it does not touch the
  `data_entry` table. **Ruled out**: this is not a DB-level cascade delete.
- No FK links Professional Travel entries to Headcount members either — the
  reporter's "PT/Headcount coupling makes sense" is a domain assumption, not
  a schema relationship. So even the "acceptable" cascade has no traced
  mechanism in the code paths checked.

**What remains unconfirmed**: the actual code path producing the reported
hide/delete behavior was not located in this pass. Two areas were not fully
excluded and are the most likely remaining suspects, given the recent
"persisted report stats" refactor on this branch (`b6c49378`, `ea99b3b9`,
`8f4846db`):

1. The report-stats computation/caching pipeline (stat buckets) may
   short-circuit or recompute incorrectly when one module is disabled,
   zeroing/hiding stats for sibling modules in the UI without touching
   underlying rows.
2. A frontend component upstream of per-module sections (not found in
   `DataManagementPage.vue`'s top-level `v-if`s) may gate a shared
   ancestor on Headcount's flag specifically.

**Candidate fixes**, per the two options the reporter proposed:

- **(A) Scope the dependency correctly (fix only real coupling, e.g. Travel).**
  No evidence found for _any_ traced coupling (Travel included) in the code
  paths reviewed — nothing to scope down yet. This fix can't be applied
  correctly until the actual mechanism is pinned down (Step 1 below); doing
  it blind risks fixing the wrong layer.
- **(B) Add a confirmation warning before deactivating Headcount.** No
  mechanism-dependent evidence needed — this is a UX safety net applicable
  regardless of root cause, and cheap to ship immediately as a stopgap.

Given (A) requires knowledge this review couldn't establish, **lead with (B)
as an immediate stopgap and use Step 1 to pin the mechanism**, then decide
whether (A) is still needed (i.e., whether a genuine unwanted coupling
exists to remove) or the bug is a display/computation defect to fix directly
(no cascade to "scope" — just a bug).

## Steps

- [ ] **Reproduce and pin the mechanism**: write a backend regression test
      that seeds `DataEntry` rows across Headcount, Equipment, Process
      Emissions, Purchases for one unit/year, `PATCH`es
      `config.modules["1"].enabled = false`, then re-fetches (a) the
      year-configuration response and (b) the report-stats endpoint(s) for
      that unit/year, and asserts the other three modules' data/stats are
      unchanged. Let it fail against current behavior to capture the actual
      diff (which field goes missing/zero).
- [ ] Based on the failing assertion, trace the exact function that produces
      the wrong output (report-stats aggregation, stat-bucket persistence,
      or a frontend computed) and confirm whether it's a real Headcount→other
      coupling or a bug unrelated to any intentional dependency.
- [ ] If a genuine unwanted coupling is found: remove/scope it so only
      Professional Travel (or nothing, if that coupling also proves
      untraceable) is affected by Headcount's enabled state.
      If it's a defect (e.g. mis-keyed cache invalidation): fix at the root
      function all callers route through, not per-module patches.
- [ ] Ship (B) regardless: add a confirmation dialog when disabling Headcount
      in the Configurator UI (`frontend/src/composables/useModuleConfig.ts`
      `updateModuleEnabled`), explaining any real remaining cross-module
      impact in plain language before the PATCH fires.
- [ ] Extend the regression test from step 1 to cover the fixed behavior and
      keep it as the permanent guard against this cascade regressing.
- [ ] Update this plan's Design section with the confirmed mechanism once
      found, per repo convention of keeping plans aligned with shipped code.
