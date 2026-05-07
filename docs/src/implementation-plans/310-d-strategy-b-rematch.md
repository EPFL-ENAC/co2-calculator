---
status: delivered
last_updated: 2026-05-06
title: "Plan 310-D Follow-up — Strategy B Rematch + Per-Module ITs"
summary: "Rematch the FK-link modules (travel, headcount, building rooms / embodied) by walking data_entry_emissions, plus per-module integration coverage."
---

# Plan 310-D Follow-up — Strategy B Rematch + Per-Module ITs

## Context

Plan 310-D's `EmissionRecalculationWorkflow.recalculate_for_data_entry_type`
(landed in PR #1027) rematches only the **JSON-link modules** —
modules whose `primary_factor_id` lives on
`data_entries.data->primary_factor_id`. The **FK-link modules**, whose
factor link lives on `data_entry_emissions.primary_factor_id`, are
skipped entirely by the existing gate
`handler.kind_field in entry.data`.

Modules affected (see the rematch table in
[emission-pipeline-flow.md](emission-pipeline-flow.md#rematch-how-factor-changes-propagate-plan-310-d)):

- **Travel** (plane / train) — factor resolved via `FactorQuery` from
  `pre_compute`-derived `haul_category` / `country_code`. One emission
  per entry.
- **Headcount** (member / student) — `FactorQuery` returns N
  sub-factors per data_entry; one emission row per sub-factor.
- **Building Rooms** — one emission row per emission_type (lighting,
  cooling, ventilation, heating_elec, heating_thermal); five rows
  per entry.
- **Building Embodied Energy** — verify shape; likely 1:N like
  rooms based on the `building_name × category` factor key.

## Goal

Add a Strategy B rematch path that:

1. Walks `data_entry_emissions` for the slice
   `(data_entry_type_id, year)`.
2. For each emission row, looks up the new factor by the OLD
   factor's classification dict.
3. Updates the row's `primary_factor_id` and recomputes `kg_co2eq`.
4. On dict miss, applies the same **strict-drop** rule from
   PR #1027: clear `primary_factor_id`, set `kg_co2eq = None`.

Same year-strict and kind→subkind→kind-only fallback rules as the
JSON-link path.

## Approach

```python
# Inside EmissionRecalculationWorkflow.recalculate_for_data_entry_type,
# after the existing JSON-link branch handles its own entries:

is_strategy_b = (
    handler.kind_field is not None
    and not any(handler.kind_field in e.data for e in entries)
)
if is_strategy_b:
    # 1. Bulk-fetch factors (same query as Strategy A).
    factors = await factor_repo.list_by_data_entry_type(det, year)
    factor_lookup = build_factor_lookup(factors, handler)

    # 2. Walk emission rows for the slice.
    emission_rows = await emission_repo.list_by_data_entry_type_and_year(
        data_entry_type_id, year
    )
    for row in emission_rows:
        old_factor = await factor_repo.get(row.primary_factor_id)
        new_id = lookup_via_classification(
            old_factor.classification, handler, factor_lookup
        )
        # Strict-drop: miss → clear FK + recompute None.
        await emission_repo.update_factor_and_recompute(row, new_id)
```

The `update_factor_and_recompute` step is an open question — see
"Open questions" below.

## Open questions

1. **Old-classification lookup vs. re-derive via `pre_compute`**.
   - **Old-classification**: simpler, single bulk fetch, no
     `Location` queries. Correct as long as the entry's underlying
     data hasn't changed since the last compute.
   - **Re-derive**: re-runs `pre_compute` per entry (DB-heavy for
     travel — fetches origin/destination `Location` again). More
     correct if entries can mutate after creation, but pricier.

   Recommend: **old-classification** for Plan 310-D's scope. Re-derive
   moves to a future "rematch on entry edit" workflow.

2. **Should we touch `entry.data` at all for Strategy B?** Today the
   Strategy A path stores `primary_factor_id` on `entry.data` for
   forward-compat. Travel today does NOT. Keep the asymmetry — don't
   start storing on travel/headcount/rooms entries.

3. **Building Embodied Energy verification.** Inspect
   `backend/app/workflows/embodied_energy.py` and confirm 1:N emission
   shape before assuming it lands in this PR. If it's actually 1:1 with
   the FK on `data_entry_emissions` only (no JSON link), it still
   belongs to this Strategy B path.

## Per-module integration tests

One PG-backed IT per (module, data_entry_type). Each test:

1. Seed: `Unit` → `CarbonReport(year=…)` → `CarbonReportModule` →
   `Factor(...)` → `DataEntry(...)` → trigger initial
   `DataEntryEmission` compute (via
   `DataEntryEmissionService.upsert_by_data_entry` or the
   POST-create handler workflow).
2. Trigger a "factor changed" event by either:
   - Calling `factor_repo.upsert_factors([new_factor])` directly with
     a different `values` payload.
   - OR posting to `/v1/sync/dispatch` with a v2 factor CSV (mirrors
     `test_plan_310b_factor_reupload_endpoint_pg.py`).
3. Run `EmissionRecalculationWorkflow.recalculate_for_data_entry_type`.
4. Assert `data_entry_emissions.kg_co2eq` reflects the new factor (or
   `None` if the factor was removed in step 2).

**Coverage matrix** (one IT per row):

| Module                         | data_entry_type            | Link kind | Notes                                                                            |
| ------------------------------ | -------------------------- | --------- | -------------------------------------------------------------------------------- |
| equipment_electric_consumption | it                         | JSON      | Already covered by Plan 310-B PG tests                                           |
| equipment_electric_consumption | scientific                 | JSON      | new IT                                                                           |
| equipment_electric_consumption | other                      | JSON      | new IT                                                                           |
| purchase                       | purchase_common            | JSON      | new IT                                                                           |
| purchase                       | purchase_additional        | JSON      | new IT                                                                           |
| external_cloud_and_ai          | external_cloud             | JSON      | new IT                                                                           |
| external_cloud_and_ai          | external_ai                | JSON      | new IT                                                                           |
| process_emissions              | process_emission           | JSON      | new IT                                                                           |
| buildings (energy_combustion)  | building_energy_combustion | JSON      | new IT                                                                           |
| buildings (rooms)              | building_room              | **JSON**  | 1:N emissions (1 per `room_type`); link is JSON, fan-out shape was the novel bit |
| buildings (embodied)           | building_embodied_energy   | **FK**    | new IT, strategy-B path                                                          |
| professional_travel            | plane                      | **FK**    | new IT, strategy-B path                                                          |
| professional_travel            | train                      | **FK**    | new IT, strategy-B path                                                          |
| headcount                      | member                     | **FK**    | new IT, strategy-B path                                                          |
| headcount                      | student                    | **FK**    | new IT, strategy-B path                                                          |

PR #1042 shipped 16 ITs total (split into two files for module-family
locality): 9 in `test_strategy_a_rematch_pg.py` (the JSON-link rows
above plus a strict-drop variant that lives next to its sibling tests
in the same file) and 7 in `test_strategy_b_rematch_pg.py` (the FK-link
rows plus a strict-drop variant for travel). The `building_room` row
moved into the Strategy B file even though the link is JSON — the 1:N
fan-out shape was the novel coverage and lives next to embodied energy
for that reason. Inline `_seed_unit_and_module` / `_initial_compute`
helpers were left duplicated rather than promoted to a `conftest.py`
shared fixture; ~30 lines of duplication across the two files was
judged not worth a dedicated commit cycle.

## Out of scope

- Changes to `ModuleHandlerService.resolve_primary_factor_id` or
  individual module handlers (rematch reuses existing factor-lookup
  semantics — it does not redefine them).
- Concurrency / locking improvements during rematch (the existing
  `claim_job` / `is_current` mechanism from Plan 310-A is reused).
- The `aggregation` job (Plan 310-D's bulk-path-pure-async work) —
  that's a separate Plan-D-Tier-2 PR.

## Critical files

| File                                                                              | Change                                                           |
| --------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `backend/app/workflows/emission_recalculation.py`                                 | Add Strategy B branch in `recalculate_for_data_entry_type`       |
| `backend/app/repositories/data_entry_emission_repo.py`                            | Add `list_by_data_entry_type_and_year(det, year)` if missing     |
| `backend/tests/integration/services/data_ingestion/test_strategy_b_rematch_pg.py` | New file — 4 strategy-B per-module ITs                           |
| `backend/tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py` | New file — 9 JSON-link per-module ITs (regression net for #1027) |
| `backend/tests/integration/services/data_ingestion/conftest.py`                   | Add `seed_module_with_emission` helper fixture                   |

## Verification

After implementation:

1. `rtk uv run pytest tests/integration/services/data_ingestion/test_strategy_b_rematch_pg.py -v`
   — all 4 Strategy B modules pass.
2. `rtk uv run pytest tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py -v`
   — regression net catches no breakage from the new branch.
3. `rtk uv run pytest tests/unit/workflows/test_emission_recalculation.py -v`
   — existing 10 unit tests still pass (no churn in the JSON path).
4. End-to-end smoke: upload a v2 travel factor CSV via `/v1/sync/dispatch`,
   confirm a previously-computed travel emission row's `kg_co2eq`
   updates without the operator needing to delete/recreate the entry.

---

**Related PRs**

- #1027 — Plan 310-D batch rematch (JSON-link modules), strict-drop semantics. This follow-up rides on top.
- #1042 — Delivered: per-module IT matrix + plan-doc realignment (see below).
- (future) — `aggregation` handler + dedup index migration (separate Plan-D Tier-2 PR).

---

## Delivered: PR #1042

The investigation phase of this PR turned up a key empirical finding
that simplified the deliverable substantially. Documented here so the
next reader can build on the right architecture.

### What actually shipped

- **No workflow code change.** `EmissionRecalculationWorkflow` is
  unchanged from PR #1027.
- **16 PG-backed integration tests** covering Plan 310-D's 14-row matrix:
  - `backend/tests/integration/services/data_ingestion/test_strategy_b_rematch_pg.py` —
    7 tests for the FK-link path (plane values, plane drop, train,
    member, student, embodied energy, building rooms 1:N).
  - `backend/tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py` —
    9 tests for the JSON-link path (equipment × 3, purchase × 2,
    external cloud, external AI, process emissions, energy combustion).
- **Plan-doc realignment** (this section).

### Why the plan's "walk data_entry_emissions" branch was not needed

The plan assumed FK-link entries (travel, headcount, embodied energy)
were skipped entirely by the rematch path. Empirically:

1. `EmissionRecalculationWorkflow` walks **every** `DataEntry` for
   `(det, year)` and calls `upsert_by_data_entry` on each. The
   gate at `handler.kind_field in entry.data` only short-circuits
   the `entry.data['primary_factor_id']` rewrite — a JSON-link
   concern. The per-entry `upsert_by_data_entry` runs unconditionally.
2. `upsert_by_data_entry` → `prepare_create` runs the handler's
   `pre_compute` (re-resolving `haul_category` from Locations,
   `country_code` from train stations, etc.) and then `_fetch_factors`
   on each `EmissionComputation`.
3. `_fetch_factors` in `data_entry_emission_service.py:343-415`
   **already** runs the live Strategy B classification query — same
   factor lookup the initial compute used. A factor whose `values`
   changed is picked up automatically; a factor whose row was deleted
   produces an empty list and the per-entry strict-drop kicks in.

The only thing missing was test coverage to make this contract durable.

### Strict-drop contract clarification

The plan's "preserve row with primary_factor_id=None, kg_co2eq=None"
language is imprecise. The actual behaviour shared by both Strategy A
and Strategy B is **delete the entry's emission rows**:

- Strategy A: bulk lookup miss → `entry.data['primary_factor_id']`
  set to `None` → `resolve_computations` returns `[]` → `upsert_by_data_entry`
  hits the `if not prepared_emissions` branch → `delete_by_data_entry_id`.
- Strategy B: `_fetch_factors` returns `[]` (classification miss
  or factor row deleted) → no `DataEntryEmission` rows produced →
  same `delete_by_data_entry_id` branch.

The dashboards surface this as "no emission for this entry", which
matches the plan's intended operator-visible signal.

### Module reclassification

The plan listed `buildings__rooms` (`DataEntryTypeEnum.building`)
under FK-link. In fact `BuildingRoomModuleHandler` declares
`kind_field='building_name'` and `subkind_field='room_type'`, both
on `entry.data` — so the existing Strategy A bulk-prefetch covers it.
The `test_building_room_factor_values_change_propagates_all_5_emissions`
test in the Strategy B file lives there because rooms emits 1:N (5
emission rows per entry, one per energy type), which is the only
genuinely new shape the FK-link conversation introduced. Verifying all
5 rows scale linearly with the factor's `ef_kg_co2eq_per_kwh` belongs
to this PR even though the lookup path itself is JSON-link.

### Files touched

| File                                                                              | Change                                                      |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `backend/app/workflows/emission_recalculation.py`                                 | No change. Plan's Strategy B branch turned out unnecessary. |
| `backend/tests/integration/services/data_ingestion/test_strategy_b_rematch_pg.py` | New file — 7 FK-link ITs incl. 1:N rooms regression.        |
| `backend/tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py` | New file — 9 JSON-link ITs (regression net for #1027).      |
| `docs/src/implementation-plans/310-d-strategy-b-rematch.md`                       | This "Delivered: PR #1042" section.                         |

### What's still on the follow-up list

The plan's "Open question 1" (old-classification lookup vs. re-derive
via `pre_compute`) collapses to "re-derive" because that's what the
existing per-entry path already does. If a future "rematch on entry
edit" workflow wants to skip the LocationService roundtrip on travel,
it could read `meta['distance_km']` from the existing
`DataEntryEmission` row — but that's a perf optimisation, not a
correctness gap.
