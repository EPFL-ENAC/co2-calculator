---
status: in-progress
issue: 2783
last_updated: 2026-09-17
title: "Equipment global percentage: one aggregate line per type instead of rewriting the reference year"
summary: "PATCH reference-percentage rewrote every snapshot line one by one (~5,700 queries, 2.3 min for 950 lines). Per the Option B decision in #2749, it now upserts one aggregate line per equipment type, reading the reference total straight from the module's already-computed stats. No schema change, no data backfill."
---

# Equipment global percentage: aggregate line per type (#2783)

## Symptom

`PATCH /carbon-reports/{id}/modules/{module_type_id}/reference-percentage`
rewrote every prefilled snapshot line individually
(`set_reference_percentage_all`, `carbon_report_module_service.py:393-429`):
one Python loop over all N snapshot entries, each going through
`DataEntryEmissionService.upsert_by_data_entry` (its own factor resolution +
DELETE + INSERT). For a 950-line equipment module that's ~5,700 sequential
statements and 2.3 minutes on stage. Full trace analysis in #2783.

## Decided semantics (#2749)

Two readings of "global percentage" were on the table; @agletiec confirmed
**Option B**: setting the global percentage collapses the reference-year
snapshot into **one aggregated line per equipment type**, not editable
line-by-line. Users can still add equipment by hand via the input form; those
manual lines are unaffected.

## Why one line per type, not one line total

The equipment UI is three separate tables/fetches
(`/modules/equipment/{scientific,it,other}`), because `data_entry_type_id`
(`scientific=10`, `it=11`, `other=12` in `data_entry.py`) is the equipment
_category_ axis and drives the report's scientific/it/other split elsewhere
(treemap, CSV). Collapsing across types would lose that. "A single line" is
scoped per type: up to 3 aggregate rows total, not 1 and not 950.

## No schema change

`data_entry_type_id` stays as-is. The existing `data` JSON keys
(`source_data_entry_id`, `percentage_of_reference_year`) get one more
combination, no new field, no new `DataEntrySourceEnum` member, no migration:

| row kind                                    | `source_data_entry_id` | `percentage_of_reference_year` |
| ------------------------------------------- | ---------------------- | ------------------------------ |
| manual (unchanged)                          | `null`                 | `null`                         |
| aggregate (new)                             | `null`                 | set                            |
| legacy per-line snapshot (phased out below) | set                    | set                            |

The presence of an aggregate row **is** the persisted mode — no separate
mode flag. This also fixes the "mode resets to per-line on reload" complaint
noted in #2783, for free.

## Reading the reference total: no fresh query

`CarbonReportModule.stats` (`carbon_report.py:196-217`) already carries
`by_emission_type` (kg per `emission_type_id`), recomputed by
`recompute_stats_many` on every write to that module. Equipment's
`data_entry_type_id` → `emission_type_id` mapping is 1:1 and enforced in
code (`DATA_ENTRY_TO_EMISSION_TYPES` in
`app/modules/emissions/registry.py:140-168`:
`scientific→equipment__scientific(80100)`, `it→equipment__it(80200)`,
`other→equipment__other(80300)`), and the equipment handler always emits
exactly one `DataEntryEmission` row per entry (`equipment/handlers.py:99-138`,
no scope fan-out). So `ref_module.stats["by_emission_type"]` already **is**
the per-type reference total — no GROUP BY needed at PATCH time.

## Backend change

`set_reference_percentage_all` rewritten:

1. Resolve the reference module: `get_calculator_report(unit_id,
reference_year)` → `get_module(...)` — existing pattern, used the same
   way in `simulator_plan_service.py:748-757`.
2. Read `ref_module.stats["by_emission_type"]`, pick out the three equipment
   leaves via `DATA_ENTRY_TO_EMISSION_TYPES`.
3. For each type present: upsert one aggregate `DataEntry` row +
   exactly one `DataEntryEmission` row (`kg = ref_total * pct / 100`).
4. Delete any leftover legacy per-line snapshot rows for this module (both
   keys set) — this is where a module last touched under the old
   implementation gets cleaned up, the first time this PATCH runs against it
   post-deploy (see "No backfill" below).
5. Existing `recompute_stats_many` + `recompute_report_stats`, unchanged.

Total cost per PATCH: one cheap module lookup, a JSON read, ≤3 upserts, a
cleanup delete, existing stats recompute. Flat regardless of entry count.

**Switching global → per-line**: delete the aggregate row(s), re-run the
existing `prefill_module_from_reference` snapshot copy to restore per-line
rows at 0% — unchanged mechanism, matches what `confirmEquipmentSwitch`
already does today.

**POST (manual add)** is untouched: `CarbonReportModuleWorkflow.create`,
`source=USER_MANUAL`, never sets `source_data_entry_id` or
`percentage_of_reference_year`. It sits next to the aggregate row(s) and
adds on top, same as it sits next to per-line rows today.

## No backfill

Reports currently sitting in global mode with per-line rows are **not**
migrated by a script. They keep working exactly as they do today — still
per-line rows, still reflecting the last-applied percentage — until someone
next calls `reference-percentage` on that module, at which point step 4
above collapses them to the aggregate shape. Nothing changes for a report
nobody touches again.

## Frontend

`PlannerYearSection.vue`:

- `equipmentReferenceTotalKg`: read from a module GET's
  `stats.by_emission_type` instead of the current three
  `?limit=1000` snapshot fetches + client-side sum
  (`fetchEquipmentSnapshotRows`, `equipmentReferenceSum`).
- Global-mode table renders however many aggregate rows exist (≤3) instead
  of the full per-type row list. No per-row slider — already the case.
- `equipmentMode` initializes from row presence (an aggregate row found →
  `global`) instead of a `ref` default that resets on reload.
- Manual add-line form and the switch-confirmation dialog: unchanged.

## Tests

- Backend: regression test asserting `set_reference_percentage_all` issues a
  fixed, small query count regardless of reference-year entry count (same
  guard style as #2050's write-path tests). Aggregate upsert produces
  exactly one row per equipment type present, correct `kg`, and a repeated
  PATCH updates those same rows in place (no duplicates). Manual entries
  survive a PATCH untouched. Switching back to per-line restores snapshot
  rows at 0%. A module with legacy per-line rows from before this change
  collapses correctly on its first post-deploy PATCH.
- Frontend: global-mode table renders aggregate rows; mode is derived from
  data and survives a simulated reload.
