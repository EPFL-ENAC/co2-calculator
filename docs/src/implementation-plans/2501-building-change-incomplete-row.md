---
status: delivered
issue: 2501
last_updated: 2026-08-28
summary: changing building_name on a buildings room row 422s — the kind-change clear nulls room_type and the #2050 fail-hard rejects the recompute, rolling back the edit; decided fix is to authorize incomplete rows (clear room_name + room_type, row computes no CO₂eq, equipment-style) instead of blocking the edit
---

# 2501 — building change on a room row must yield an incomplete row, not a 422

## Root cause

Inline table edits send single-field PATCHes
(`ModuleTable.vue` `saveEdit` → `patchItem({[col.field]: value})`). For the
buildings room handler, `building_name` is the `kind_field` and `room_type`
the `subkind_field` (`backend/app/modules/buildings/handlers.py`), so a
`{building_name}` PATCH triggers `clear_dependent_fields_on_kind_change`
(`backend/app/services/module_handler_service.py`), which nulls `room_type`.
The emission recompute then hits `resolve_building_rooms`
(`backend/app/modules/buildings/emissions.py`), where the empty `room_type`
raises `EmissionTypeResolutionError`; the update workflow maps the
`ValueError` to HTTP 422 and rolls back
(`backend/app/workflows/carbon_report_module.py`). Net: nobody can change
the building on an existing room row. No data is corrupted (full rollback).

This is not a #2050 regression in substance: before the fail-hard (shipped
to stage 2026-08-27), the same flow silently nulled `room_type` and zeroed
the row's emissions. The guardrail made an old silent bug loud.

Reproduced (stage, report 456): `PATCH …/buildings/building/<id>` with
`{"building_name": "BCH"}` → 422 `No emission type for building room_type ''`.

## Decided approach (maintainer, issue comment 2026-08-28)

Authorize an incomplete row. When `building_name` changes, the stored
`room_name` cannot survive (a room belongs to exactly one building), so the
backend clears `room_name` and `room_type`; the row persists without an
emission — same semantic as an incomplete equipment row (no factor → no
emission rows → blank kg cell). The alternative (disable building edits)
was considered and rejected.

Key precedents this mirrors:

- Equipment: `resolve_computations` returns `[]` when no factor resolves;
  `prepare_create` treats an empty leaf list as "a real answer", and
  `upsert_by_data_entry` deletes stale emission rows even when the new set
  is empty — the row cleanly loses its kg_co2eq.
- The room dialog (`useBuildingRoomDynamicOptions.ts`) already clears
  room fields client-side on building change.
- The frontend already has generic incomplete-row rendering:
  `submoduleConfig.requiredFieldIds` → `row-incomplete` class
  (`ModuleTable.vue` `isComplete`).

## Backend changes

1. **Clear `room_name` on kind change.** Extend
   `clear_dependent_fields_on_kind_change` with a handler-declared
   `kind_dependent_fields: tuple[str, ...] = ()` on `BaseModuleHandler`,
   cleared under the same conditions as the subkind (kind changed, field
   not in the request). `BuildingRoomModuleHandler` declares
   `("room_name",)`. `room_type` is already cleared as the subkind.
   `BuildingRoomHandlerUpdate` accepts `room_name=None` as-is (its
   `_non_empty` validator skips `None`).

2. **Incomplete gate in emission resolution.** In
   `resolve_building_rooms`, before the room_type validity check: if
   `room_name` or `room_type` is missing/empty, return `[]` (no leaves →
   no emission rows → stale rows deleted by the upsert). The existing
   raises stay for _present but invalid_ values: an unknown `room_type`
   still raises, and a `room_name` that resolves no `BuildingRoom`
   ref-data row still fails hard in the formula (bad data ≠ incomplete).
   This also un-breaks recalc over legacy rows corrupted by the pre-#2050
   silent clear (room_type null, stale room_name): they become visible
   incomplete rows instead of per-entry recalc failures.

3. **Embodied-energy companion: no change.** `EmbodiedEnergyWorkflow.
_reconcile` is already a pure function of the parents' `room_name`s: a
   parent losing its room_name drops its companion, re-picking a room
   recreates it. Pinned by test, not changed.

## Frontend changes

4. **Incomplete-row rendering.** Add
   `requiredFieldIds: ['building_name', 'room_name', 'room_type']` to the
   Building submodule config (`frontend/src/constant/module-config/
buildings.ts`) so the generic `row-incomplete` styling and completeness
   logic apply. The kg cell is blank because the backend returns
   `kg_co2eq: null`.

5. **Inline room pick sends the room's type.** When the user picks a
   `room_name` inline, PATCH `{room_name, room_type}` with the type from
   the picked room's ref-data (the building-rooms endpoint returns
   `room_type` per room) — mirroring the dialog's autofill. Without this,
   a room re-pick after a building change leaves the row incomplete until
   the user separately sets `room_type`, and a plain room change silently
   keeps the old room's type (a lab priced as an office). Payload/option
   mapping extracted to `frontend/src/utils/buildingRoomInline.ts`.

6. **Inline `room_name` options source (investigated: wrong source).**
   `ModuleInlineSelect` fed the Local column from the factor taxonomy's
   subkind options — which for buildings are room _types_
   ("auditoriums", …), not room names. Picking one PATCHed
   `room_name: "auditoriums"` → unknown room → the deep formula 422
   (the issue's second repro). The Local select now loads the ref-data
   rooms of the row's current building via `buildingRoomStore.fetchRooms`
   (store-cached per building, 60 s), the same source as the dialog, and
   refreshes when the row's building changes.

## Tests (regression-first)

- Backend (pytest, pg): PATCH `{building_name}` on a complete room row →
  200, `room_name`/`room_type` null in response, emission rows deleted,
  `kg_co2eq` null. Then PATCH `{room_name, room_type}` → row complete,
  emissions recomputed. Companion embodied row deleted on the first PATCH,
  recreated on the second.
- Backend unit: the clear function nulls declared `kind_dependent_fields`
  on kind change only (same-value PATCH untouched; explicit values in the
  request win).
- Backend: `resolve_building_rooms` returns `[]` for missing
  room_name/room_type, still raises for an invalid room_type.
- Frontend (Playwright): inline building change renders the row as
  incomplete with an empty kg cell; picking a room of the new building
  completes it. Component test for the packed `{room_name, room_type}`
  PATCH payload.

## Out of scope / follow-ups

- Write-time validation that `(building_name, room_name)` matches
  `BuildingRoom` ref-data (would turn the deep formula failure for
  unknown rooms into a clean 422 naming the field). Park as its own
  issue.
- Inline-select revert-on-error (the select keeps the failed value after
  a 422, `error: false`). Mostly moot once this flow stops 422ing.
- CSV/import paths: unchanged — `pre_compute` warnings for unresolvable
  rooms remain.
