---
status: in-progress
issue: 878
last_updated: 2026-08-17
title: "Reuse EmbodiedEnergyWorkflow logic for CSV/bulk building ingestion"
summary: "CSV/bulk building-room ingestion never derives building_embodied_energy rows (#878) — only the single-item CRUD API path does, via EmbodiedEnergyWorkflow.post_create/update/delete. A prior attempt (PR #2121) fixed the symptom but reimplemented the derivation logic inside BaseCSVProvider instead of reusing the workflow. This plan extracts the shared derivation logic (fixing a latent bug where it silently depends on a frontend-only field), keeps #2121's simpler synchronous/full-replace placement, and reuses it from both the CRUD and CSV paths."
---

# Implementation Plan: Reuse `EmbodiedEnergyWorkflow` logic for CSV/bulk building ingestion

> **Issue: [#878](https://github.com/EPFL-ENAC/co2-calculator/issues/878)**
> — the title/body is unrelated (Results-page feedback), the actual report
> is buried in a comment thread from `@martina-gallato`: _"le calcul des
> constructions et rénovations ne s'effectue pas lors de l'ingestion des
> CSV, mais uniquement lorsque je saisis des données manuellement"_ — i.e.
> this exact gap, plus an explicit call that old data will not be
> retroactively recalculated, only new ingests going forward. That framing
> (no backfill promised to the reporter) should be revisited before merge
> against the "DB persists, backfills apply" project default — flag it to
> the maintainers rather than silently deciding either way.
>
> **Prior attempt: [PR #2121](https://github.com/EPFL-ENAC/co2-calculator/pull/2121)**
> (open, `BenBotros`, CI green, no tests) already fixes the symptom — **will
> not be merged** (decided below in §5), but its structural decisions are
> worth reusing. See §0 for what it got right and what this plan changes;
> §5 for landing this as a fresh implementation against current `dev`.
>
> **Touches recalculation/pipeline internals** (`backend/app/workflows/`,
> `backend/app/services/data_ingestion/`, `backend/app/tasks/`) — per
> `guardrails.md`, do not implement without a written plan reviewed by both
> maintainers. This file is that plan; get it reviewed before writing code.
> Target branch: `fix/pipeline-debug`, not `dev`, per project convention for
> pipeline-chain work.

## 0. What PR #2121 already got right (and wrong)

Read in full (`gh pr diff 2121`, 4 files, +116/-11, no test files). It:

- Adds `DERIVED_DATA_ENTRY_TYPES = {building: [building_embodied_energy]}`
  (`app/models/module_type.py`) and folds it into
  `_delete_existing_entries_for_module_per_year`'s `valid_entry_types` so a
  det-pinned building re-upload deletes stale derived rows along with the
  stale rooms — **full delete-then-recreate, not a diff**. This is simpler
  than this plan's earlier diff-and-sync draft and fits the file's existing
  "per-year CSV is a complete export" precedent
  (`base_csv_provider.py:786-801`). **Worth keeping.**
- Runs the derivation **synchronously, inline**, at the tail of
  `_finalize_and_commit` (`_create_embodied_energy_companions`) — not as a
  new chained job. Since derived rows don't need priced emissions to
  exist (that comes from the recalc chain right after), and the row count
  is bounded by the CSV itself, there's no real need for a separate async
  step. **Worth keeping** — it avoids adding a new job type, a new
  `DedupConfig`, and a migration, which is a much smaller, lower-risk diff
  for something touching pipeline internals.
- Fetches the just-inserted `building` rows back via a new
  `DataEntryRepository.list_by_creator_and_type(created_by_id, type)`
  (`data_entry_repo.py`) — necessary because `bulk_copy` (used for the main
  batch insert) never populates `.id`
  (`app/repositories/data_entry_repo.py:104-134`), and the derived entry's
  `data.data_entry_id` FK-link needs the real id. **Worth keeping.**
- Prefetches the whole `BuildingRoom` table once
  (`BuildingRoomRepository.list_rooms()`) instead of one query per row —
  already avoids the ~20k-row N+1 for the CSV path itself. **Worth
  keeping** (independently, `BuildingRoomModuleHandler.pre_compute`'s
  existing per-row `get_room` call for the _interactive_ recalc path still
  has the N+1 — out of scope for #878, flagged as a possible follow-up in
  §2.2, not bundled into this fix).
- Fans out a **parallel sibling** `emission_recalc(building_embodied_energy)`
  job next to `emission_recalc(building)`
  (`_chain_emission_recalc_for_data_ingest`,
  `app/tasks/ingestion_tasks.py:492-...`) instead of chaining it
  sequentially after. Safe specifically because derived rows already
  exist (created synchronously, step above) by the time the async chain
  fires — no ordering dependency between the two siblings. **Worth
  keeping** — this plan's earlier draft over-built a 3-deep sequential
  chain to solve an ordering problem that doesn't exist once creation is
  synchronous.
- **What it gets wrong — the actual point of this plan**:
  `_embodied_energy_companion` (a new `@staticmethod` on `BaseCSVProvider`)
  reimplements the `building` → `building_embodied_energy` transform from
  scratch instead of calling `EmbodiedEnergyWorkflow`. Two independent
  implementations of the same derivation _will_ drift — the guardrail this
  whole plan exists to uphold. Concretely it already has drifted: it
  resolves `room_surface_square_meter` via the room-table lookup **and**
  falls back to `parent.data.get("room_surface_square_meter")` — dead code
  for CSV rows (that key is never present, per §1's diagnosis) copied over
  from a misreading of the CRUD path's original (also-buggy)
  `_make_building_embodied_energy_data`. It also puts building-specific
  logic (`BuildingRoomRepository` import, building-only branch) inside
  `BaseCSVProvider`, the generic base every module's CSV ingestion goes
  through — a layering smell (mirrors, don't invent: buildings-specific
  logic belongs behind `EmbodiedEnergyWorkflow`/a buildings service, not in
  the shared CSV base). And it ships with **zero tests**, against the
  "every bug fix ships with a regression test" guardrail.
- **Verdict**: reuse §0's structural decisions (delete-then-recreate,
  synchronous inline, parallel recalc sibling, `list_by_creator_and_type`),
  replace `_embodied_energy_companion` with a call into the shared,
  corrected `EmbodiedEnergyWorkflow` resolver from §2.1, and move the
  buildings-specific orchestration out of `BaseCSVProvider` into
  `EmbodiedEnergyWorkflow` itself (called from one small, generic hook in
  `_finalize_and_commit` — `DERIVED_DATA_ENTRY_TYPES`-driven, not
  buildings-hardcoded, so the base class stays module-agnostic). Add the
  missing tests.

## 1. Diagnosis

`EmbodiedEnergyWorkflow.post_create/post_update/post_delete`
(`backend/app/workflows/embodied_energy.py`) derives a
`building_embodied_energy` `DataEntry` whenever a `building` (room) entry is
created/updated/deleted — but it is wired in **only** at the single-item CRUD
API layer (`backend/app/api/v1/carbon_report_module.py:892,987,1043`, called
right after `CarbonReportModuleWorkflow.create/update/delete`). The CSV bulk
path (`backend/app/services/data_ingestion/base_csv_provider.py`,
`ModulePerYearCSVProvider`) never references it — confirmed by grep and by
the test suite's own docstring
(`backend/tests/integration/services/data_ingestion/test_buildings_csv_pg.py:20-23`):
_"`building_embodied_energy` — derived: rows are created post-hoc by
`EmbodiedEnergyWorkflow.post_create`... No CSV ingest path."_ So today, a
building room CSV upload produces zero embodied-energy rows; only rooms
created one at a time through the UI form get one.

**A second, deeper bug surfaced during investigation and must be fixed as
part of the same change, not worked around:**
`EmbodiedEnergyWorkflow._make_building_embodied_energy_data` reads
`room_surface_square_meter` straight off the source `building` entry's
`.data` dict. That field is **not** a declared field of
`BuildingRoomHandlerCreate` (`backend/app/modules/buildings/data_entries.py:57-62`
has only `building_name`, `room_name`, `room_type`,
`room_allocation_ratio`, `note`) — it is a real, resolved-from-reference-data
value (`BuildingRoomModuleHandler.pre_compute`,
`backend/app/modules/buildings/handlers.py:72-109`, calls
`BuildingRoomService.get_room(room_name=...)`), never persisted on the
`building` row (per the "don't store derived values" invariant, and
confirmed: `DataEntryEmissionService`'s `ctx` merge never writes `pre_compute`
results back to `data_entry.data`,
`backend/app/services/data_entry_emission_service.py:484-495`). The only
reason the single-item CRUD path "works" today is that the frontend's room
picker smuggles the value through as an extra, undeclared payload field
(`frontend/src/composables/useBuildingRoomDynamicOptions.ts:138`,
`form['room_surface_square_meter'] = match.room_surface_square_meter`), which
`DataEntryPayloadMixin.unflatten_payload`
(`backend/app/schemas/data_entry.py:37-48`) happily carries into `.data`
unfiltered. CSV ingestion filters incoming columns to each handler's
_declared_ DTO fields
(`base_csv_provider.py:1227-1231`, `filtered_row = {k: v for k, v in
row.items() if k in expected_columns...}`), so even a CSV with an extra
`room_surface_square_meter` column would never reach `.data`. Simply wiring
CSV rows into the existing helper unchanged would silently no-op forever
(every row hits the `if room_surface_square_meter is None: return None`
guard) — a second silent fallback stacked on the first. The shared logic
must resolve the surface itself via `BuildingRoomService`, the same call
`pre_compute` already makes, instead of trusting an upstream caller to have
passed it in.

## 2. Recommended approach

**Core principle: one shared "how do I build a `building_embodied_energy`
payload from a `building` entry" function, invoked by two orchestration
shapes** — synchronous single-item (existing) and async bulk-diff (new) —
mirroring the codebase's existing sync-vs-bulk split for emissions
themselves (`DataEntryEmissionService.upsert_by_data_entry` for single-item
vs `EmissionRecalculationWorkflow` for bulk/recalc). This is not new
duplication; it's the same shape the rest of the pipeline already uses.

### 2.1 Fix and extract the shared derivation logic (`embodied_energy.py`)

In `backend/app/workflows/embodied_energy.py`, replace
`_make_building_embodied_energy_data` with a session-aware version that
resolves the room surface itself:

```python
async def _resolve_building_embodied_energy_data(
    room_cache: dict[str, BuildingRoom] | None,
    session: AsyncSession,
    data_entry_id: int,
    data: dict,
) -> dict | None:
    building_name = data.get("building_name")
    room_name = data.get("room_name")
    if not building_name or not room_name:
        return None
    if room_cache is not None:
        room = room_cache.get(room_name)
    else:
        room = await BuildingRoomService(session).get_room(room_name=room_name)
    if room is None or room.room_surface_square_meter is None:
        return None
    return {
        "data_entry_id": data_entry_id,
        "building_name": building_name,
        "room_surface_square_meter": room.room_surface_square_meter,
    }
```

Make it a module-level function (or `@staticmethod`) so both the workflow
and the new bulk step import the exact same code — not a copy.
`EmbodiedEnergyWorkflow._post_create_building`/`_post_update_building` call
it (with `room_cache=None`, so it falls back to the direct `get_room` call —
no cache needed for a single room) in place of the old
`.data.get("room_surface_square_meter")` read.
`_get_embodied_energy_entry_id` (lines 174-185) is already pure
session/id-based lookup logic — reused as-is by the bulk step too (or given
a bulk sibling, see §2.2).

Once this ships, remove the now-redundant frontend autofill
(`useBuildingRoomDynamicOptions.ts` lines 44, 57, 138 setting
`room_surface_square_meter` on the form) — the backend resolves it, the
field was never meant to be client-supplied (guardrail: backend is the
single source of truth for every transform).

### 2.2 Bulk derived-entry creation — reuse #2121's placement, not its transform

Add `EmbodiedEnergyWorkflow.create_derived_entries_for(parent_entries:
list[DataEntry]) -> int`, taking the just-inserted `building` `DataEntry`
rows (already fetched with real ids — see below) and bulk-inserting their
`building_embodied_energy` derived entries:

- **No diff/reconcile logic needed.** #2121's delete-then-recreate strategy
  (§0) means every call to this method only ever sees _new_ parent rows —
  cleanup of stale derived rows already happened via
  `_delete_existing_entries_for_module_per_year`'s `DERIVED_DATA_ENTRY_TYPES`
  inclusion (kept as-is from #2121). So this is a straight
  map-and-bulk-insert, not a create/update/delete reconciliation — simpler
  than this plan's earlier draft.
- **Performance — no per-row `BuildingRoomService.get_room` call.** With
  ~20k rooms, one query per `building` row is exactly the ingest failure
  mode to avoid — #2121 already solved this for the CSV path with one
  `BuildingRoomRepository.list_rooms()` call up front
  (`building_room_service.py:29-38`/`building_room_repo.py:43-56` — the
  whole reference table is the cache, no per-slice filtering needed). Keep
  that: build `{room_name: BuildingRoom}` once, pass it into
  `_resolve_building_embodied_energy_data` (§2.1) as `room_cache` so the
  shared resolver does an in-memory lookup instead of a query per row —
  same function, same fix, now used by both the interactive and bulk
  paths instead of #2121's bespoke `surface_by_room` dict.
  _(Optional follow-up, not bundled into #878: `BuildingRoomModuleHandler.
pre_compute` still does one `get_room` call per entry on every `building`
  recalc job, CSV-triggered or not — the same `prefetch_slice` bulk-cache
  pattern `ProfessionalTravelPlaneModuleHandler` already uses
  (`professional_travel/handlers.py:127-164`, wired through
  `EmissionRecalculationWorkflow` at `emission_recalculation.py:125`) would
  fix that too, but it's a separate pre-existing N+1, unrelated to the
  CSV-ingest gap this issue reports — keep this fix minimal and self
  contained, file it separately if worth doing.)_
- `EmbodiedEnergyWorkflow(session).create_derived_entries_for(parents)`:
  builds the room cache, calls `_resolve_building_embodied_energy_data` per
  parent, drops the `None`s (missing room/no ref-data — same "skip, don't
  default" semantic as the interactive path), and bulk-inserts via
  `DataEntryService.bulk_copy` (`data_entry_service.py:312-335` — matches
  the file's existing bulk-insert idiom; no ids needed back from this
  insert, so `bulk_copy`'s known id gap is a non-issue here).

### 2.3 Wire it into `base_csv_provider.py` (generic hook, not buildings-specific)

Keep #2121's placement (synchronous, tail of `_finalize_and_commit`) and its
`emission_recalc` fan-out change, but drive both off
`DERIVED_DATA_ENTRY_TYPES` instead of hardcoding "buildings" into the base
class, so `BaseCSVProvider` stays module-agnostic (only `buildings` has an
entry in that map today, but the base class shouldn't need to know that):

- `base_csv_provider.py`, `_finalize_and_commit`: where #2121 added
  `_create_embodied_energy_companions`, instead add a small generic
  `_create_derived_entries` that — for each `derived_type` in
  `DERIVED_DATA_ENTRY_TYPES.get(pinned_det, [])` — fetches this job's newly
  written parent rows via `DataEntryRepository.list_by_creator_and_type`
  (#2121's addition, kept as-is: `created_by_id=self.job_id,
data_entry_type_id=pinned_det`) and delegates to the type-specific
  deriver. For now there's exactly one deriver
  (`EmbodiedEnergyWorkflow.create_derived_entries_for`, buildings only), so this
  can be a one-entry `dict[DataEntryTypeEnum, Callable]` map or a single
  `if derived_type == DataEntryTypeEnum.building_embodied_energy` branch —
  whichever reads simpler; don't build a plugin registry for one caller
  (YAGNI).
- `ingestion_tasks.py`, `_chain_emission_recalc_for_data_ingest`: keep
  #2121's fan-out of a parallel `emission_recalc` sibling per
  `DERIVED_DATA_ENTRY_TYPES.get(pinned, [])` entry — already generic
  (reads the map, not a buildings check), no change needed there beyond
  what #2121 already did.

This only touches the `buildings` module in practice (the only key in
`DERIVED_DATA_ENTRY_TYPES` today) but doesn't hardcode that into the base
CSV provider — a second derived module type is a map entry + deriver
function, not a new branch in `BaseCSVProvider`.

### 2.4 Keep the single-item plumbing as-is

`EmbodiedEnergyWorkflow.post_create/post_update/post_delete` and their call
sites in `carbon_report_module.py` stay as the **synchronous** path — a user
creating one room in the UI still sees the derived embodied-energy entry
immediately in the same response, exactly like `upsert_by_data_entry`
computes that single entry's emissions synchronously while bulk CSV rows
wait for the async `emission_recalc` job. Two invocation shapes calling the
one shared `_resolve_building_embodied_energy_data` is the established
sync/bulk split, not competing implementations — no backward-compat
violation.

## 3. Critical files

Smaller footprint than the earlier job-chaining draft — no new job type, no
`DedupConfig`, no migration:

- `backend/app/workflows/embodied_energy.py` — fix + extract
  `_resolve_building_embodied_energy_data` (§2.1, now `room_cache`-aware),
  add `create_derived_entries_for` (§2.2).
- `backend/app/services/data_ingestion/base_csv_provider.py` — replace
  #2121's `_create_embodied_energy_companions`/`_embodied_energy_companion`
  with the generic `_create_derived_entries` hook (§2.3) that calls into
  `EmbodiedEnergyWorkflow`; drop the `BuildingRoomRepository` import (no
  longer needed here — buildings-specific lookups move behind the
  workflow).
- `backend/app/tasks/ingestion_tasks.py` — keep #2121's
  `DERIVED_DATA_ENTRY_TYPES` fan-out change in
  `_chain_emission_recalc_for_data_ingest` as-is.
- `backend/app/models/module_type.py` — keep #2121's `DERIVED_DATA_ENTRY_TYPES`
  map and its use in `_delete_existing_entries_for_module_per_year`'s
  `valid_entry_types` as-is.
- `backend/app/repositories/data_entry_repo.py` — keep #2121's
  `list_by_creator_and_type` as-is.
- `frontend/src/composables/useBuildingRoomDynamicOptions.ts` — drop the
  now-redundant `room_surface_square_meter` autofill once the backend
  resolves it itself.
- `backend/tests/integration/services/data_ingestion/test_buildings_csv_pg.py`
  — update the docstring (no longer "no CSV ingest path"); add the coverage
  listed in §4 (missing from #2121).

## 4. Verification

- New unit tests for `_resolve_building_embodied_energy_data` (ref-data hit
  / miss / missing `room_name`, `room_cache` hit vs `None`-cache DB
  fallback) and `create_derived_entries_for` (bulk-insert shape, skip-on-missing
  semantics) — mirrors
  `tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py`'s
  style. None of this exists in #2121 — it shipped with zero tests.
- Regression test pinning the room-lookup query count for a CSV ingest of N
  `building` rows: assert one `list_rooms()` call regardless of N, not
  O(N) — the concrete "20k rooms must not mean 20k queries" contract from
  this conversation.
- Extend `test_buildings_csv_pg.py`'s existing `dispatch_csv_and_wait`
  chain-wiring test to assert `building_embodied_energy` rows exist after a
  building CSV ingest with correct `kg_co2eq`; add a re-dispatch (reupload)
  case asserting stale derived rows are replaced, not duplicated (exercises
  #2121's delete-then-recreate path end to end).
- Regression test for the frontend-smuggling bug: a `building` entry
  created via a raw API payload (no `room_surface_square_meter` field, as a
  non-JS client would send) must now also get a correct derived entry — today
  it silently wouldn't, on _either_ path.
- Run `uv run pytest` on the touched files locally; `make ci` (ruff + ty +
  vue-tsc) before pushing, per guardrails — not `make test-cov`/full suite
  unless asked.

## 5. Path to landing

**Decision: #2121 will not be merged.** Reimplement from current `dev`
fresh — a new branch off `dev` (per the `fix/pipeline-debug` convention for
pipeline-chain work), not a checkout or rebase of #2121's branch. #2121
stays useful as prior art (§0 credits the structural decisions worth
repeating) but the code lands as new commits against current `dev`, so it
picks up whatever's landed there since #2121 was opened (2026-08-14) instead
of inheriting its branch point. Comment on #2121 linking this plan and
closing it in favor of the new PR, so `BenBotros` isn't left wondering why
their green PR went stale — referencing both #878 and #2121 from the new
PR's description.

Before writing code: diff current `dev` against #2121's four touched files
(`module_type.py`, `data_entry_repo.py`, `base_csv_provider.py`,
`ingestion_tasks.py`) to confirm none of them drifted since 2026-08-14 in a
way that changes §2's design (e.g. another PR touching
`_delete_existing_entries_for_module_per_year` or
`_chain_emission_recalc_for_data_ingest` in the meantime).
