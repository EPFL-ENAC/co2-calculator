---
status: in-progress
issue: 1661
last_updated: 2026-07-05
title: "Remove primary_factor_id from DataEntry.data — implementation plan"
summary: "Task-by-task execution plan for the approved spec 1661-remove-primary-factor-id.md: bottom-up (repo → services → workflows → routes), checkbox-tracked, resumable across sessions."
---

# Remove `primary_factor_id` from `DataEntry.data` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [1661-remove-primary-factor-id.md](1661-remove-primary-factor-id.md) — read it first.

**Goal:** Stop persisting the resolved factor id in `DataEntry.data`; resolve
factors on demand through a memoized `FactorResolver`; then (Phase 2) flip
factor CSV reupload to replace-semantics and delete the stale-factor
machinery.

**Architecture:** The entry's classification fields are the sole source of
truth; the matched factor is derived state. A new
`app/services/factor_resolver.py` owns all in-memory resolution (promoted
from the Plan-310D lookup code in `emission_recalculation.py`). Every
current writer/reader of `data["primary_factor_id"]` switches to the
resolver, bottom-up: service → emission compute → recalc workflow → CSV
ingest → API/enrichment → dead-code sweep.

**Tech stack:** FastAPI + SQLModel/SQLAlchemy async, PostgreSQL, pytest
(`uv run pytest`), openapi-typescript for `frontend/src/types/api/openapi.d.ts`.

## How to resume this plan (session handoff)

1. Worktree: `/Users/guilbert/works/git/github/co2-calculator/.claude/worktrees/remove-primary-factor-id`,
   branch `fix/1661-remove-primary-factor-id` (based on `fix/1661-refactor`).
2. Read the spec, then this file. Find the first unchecked `- [ ]` step.
3. Tick checkboxes as you complete steps; update the **Progress log** at the
   bottom of this file and commit the plan file together with each task's
   code commit.
4. Backend commands run from `backend/`: `uv run pytest …`, lint/type-check
   via `make -C backend lint type-check` (verify target names in
   `backend/Makefile` on first use).

## Global constraints

- Conventional commits, **no** Claude attribution trailers.
- Backend functions ≤40 lines, ≤2 nesting levels; extract helpers.
- Wrap SQLModel column refs in `col()`; no bare `# type: ignore` (always
  `[code]`); no `assert` for narrowing (raise `ValueError`).
- No inline imports; imports at top of file.
- No backward-compat shims, no dual paths: when the resolver path ships,
  the stored-id path is deleted in the same task.
- Every behavior change lands with a test in the same commit.
- Do not hand-author Alembic migrations (none are expected in this plan;
  the DB schema does not change in Phase 1 — `primary_factor_id` lives in
  a JSON blob, and Phase 2 only deletes rows).
- The user runs the full test suites; each task lists the exact commands so
  they (or CI) can run them. Lint + type-check must pass before every commit.

---

## Phase 1 — dynamic resolution

### Task 1: `FactorResolver` service

**Files:**
- Create: `backend/app/services/factor_resolver.py`
- Test: `backend/tests/unit/services/test_factor_resolver.py`

**Interfaces (later tasks rely on these exact signatures):**

```python
class FactorResolver:
    def __init__(self, session: AsyncSession) -> None: ...
    async def resolve(
        self,
        handler: "ModuleHandler",
        data: dict,
        data_entry_type: DataEntryTypeEnum,
        year: int,
    ) -> Factor | None: ...
    async def factors_by_id(
        self, data_entry_type: DataEntryTypeEnum, year: int
    ) -> dict[int, Factor]: ...
```

Semantics are exactly today's in-memory rematch rules
(`emission_recalculation.py:397-500` + map building at `:126-165`):

- `(kind, subkind)` exact match → `(kind, None)` fallback; miss → `None`.
- Override-key-first for handlers with `kind_field_override`
  (single override match wins; several disambiguate by kind; kind fallback
  restricted to "average" rows without an override code; ambiguity raises
  `ValueError`).
- Duplicate `(kind, subkind)` keys: first row wins (`setdefault`), same as
  today's recalc. Phase 2 makes duplicates impossible.
- `handler.kind_field is None` or kind value absent/empty → `None`.

- [x] **Step 1.1: Write failing unit tests**

Create `backend/tests/unit/services/test_factor_resolver.py`. Model factors
as real `Factor` objects; stub the repository call by monkeypatching
`FactorRepository.list_by_data_entry_type` (pattern used in
`backend/tests/unit/workflows/test_emission_recalculation.py` for the
lookup tests — port those cases here). Minimum cases:

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.schemas.data_entry import BaseModuleHandler
from app.services.factor_resolver import FactorResolver


def _factor(fid: int, det: DataEntryTypeEnum, year: int, classification: dict) -> Factor:
    return Factor(
        id=fid,
        data_entry_type_id=det.value,
        emission_type_id=1,
        classification=classification,
        values={"kw": 1.0},
        year=year,
    )


EQUIPMENT = DataEntryTypeEnum.scientific_equipment  # any kind/subkind handler
HANDLER = BaseModuleHandler.get_by_type(EQUIPMENT)


@pytest.mark.asyncio
async def test_exact_kind_subkind_match():
    factors = [
        _factor(1, EQUIPMENT, 2025, {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"}),
        _factor(2, EQUIPMENT, 2025, {HANDLER.kind_field: "Mill"}),
    ]
    with patch(
        "app.services.factor_resolver.FactorRepository.list_by_data_entry_type",
        new=AsyncMock(return_value=factors),
    ):
        resolver = FactorResolver(session=AsyncMock())
        got = await resolver.resolve(
            HANDLER,
            {HANDLER.kind_field: "Mill", HANDLER.subkind_field: "CNC"},
            EQUIPMENT,
            2025,
        )
    assert got is not None and got.id == 1


@pytest.mark.asyncio
async def test_kind_only_fallback_when_subkind_misses(): ...
    # same fixture; data subkind "Unknown" → resolves factor 2

@pytest.mark.asyncio
async def test_miss_returns_none(): ...
    # kind "Absent" → None

@pytest.mark.asyncio
async def test_kind_field_none_returns_none(): ...
    # handler without kind_field (build a stub handler) → None, repo NOT called

@pytest.mark.asyncio
async def test_memoized_single_bulk_select(): ...
    # two resolve() calls, assert list_by_data_entry_type awaited exactly once

@pytest.mark.asyncio
async def test_override_single_match_wins(): ...
@pytest.mark.asyncio
async def test_override_multiple_disambiguated_by_kind(): ...
@pytest.mark.asyncio
async def test_override_ambiguous_raises_value_error(): ...
@pytest.mark.asyncio
async def test_kind_fallback_requires_single_average_row(): ...
    # port assertions 1:1 from the _lookup_factor_id_with_override tests in
    # backend/tests/unit/workflows/test_emission_recalculation.py
```

(Replace `...` bodies with real code when writing the file — port the
existing recalc lookup test cases; they already cover every branch.
`EQUIPMENT`: pick the det the existing tests use if different.)

- [x] **Step 1.2: Run tests, verify they fail with `ModuleNotFoundError`**

```bash
cd backend && uv run pytest tests/unit/services/test_factor_resolver.py -x -q
```

- [x] **Step 1.3: Implement `backend/app/services/factor_resolver.py`**

```python
"""On-demand factor resolution (plan 1661).

The entry's classification fields are the source of truth; the matching
factor is derived state — resolved when needed, memoized per instance,
never persisted on the entry.  Instance lifetime: one API request or one
recalc slice.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository

if TYPE_CHECKING:
    from app.schemas.data_entry import ModuleHandler


@dataclass
class _FactorMaps:
    by_id: dict[int, Factor]
    by_kind_subkind: dict[tuple[str, str | None], int]
    override_lookup: dict[str, list[tuple[int, str]]]
    kind_lookup: dict[str, list[tuple[int, str | None]]]


class FactorResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._maps: dict[tuple[int, int], _FactorMaps] = {}

    async def factors_by_id(
        self, data_entry_type: DataEntryTypeEnum, year: int
    ) -> dict[int, Factor]:
        maps = await self._get_maps(data_entry_type, year)
        return maps.by_id

    async def resolve(
        self,
        handler: "ModuleHandler",
        data: dict,
        data_entry_type: DataEntryTypeEnum,
        year: int,
    ) -> Optional[Factor]:
        if handler.kind_field is None:
            return None
        maps = await self._get_maps(data_entry_type, year)
        if handler.kind_field_override is not None:
            factor_id = _resolve_with_override(
                data,
                kind_field=handler.kind_field,
                override_field=handler.kind_field_override,
                override_lookup=maps.override_lookup,
                kind_lookup=maps.kind_lookup,
            )
        else:
            factor_id = _resolve_kind_subkind(
                data,
                kind_field=handler.kind_field,
                subkind_field=handler.subkind_field,
                by_kind_subkind=maps.by_kind_subkind,
            )
        if factor_id is None:
            return None
        return maps.by_id.get(factor_id)

    async def _get_maps(
        self, data_entry_type: DataEntryTypeEnum, year: int
    ) -> _FactorMaps:
        key = (data_entry_type.value, year)
        maps = self._maps.get(key)
        if maps is None:
            factors = await FactorRepository(self.session).list_by_data_entry_type(
                data_entry_type, year
            )
            maps = _build_maps(factors)
            self._maps[key] = maps
        return maps
```

Module-level helpers `_build_maps`, `_resolve_kind_subkind`,
`_resolve_with_override`: **move the bodies verbatim** from
`emission_recalculation.py` — map building from lines 126-165 (both the
override and kind/subkind branches, keyed off the handler in `_build_maps`'s
callers, so `_build_maps(factors)` builds *all* maps unconditionally:
`by_id`, `by_kind_subkind` with `setdefault`, `override_lookup`,
`kind_lookup`; it needs the kind/subkind/override field names — pass them
in: `_build_maps(factors, kind_field=..., subkind_field=..., override_field=...)`
and store maps per `(det, year)` only because handler is 1:1 with det —
`BaseModuleHandler.get_by_type(det)` inside `_get_maps` provides the field
names). `_resolve_kind_subkind` = body of `_lookup_factor_id`
(`emission_recalculation.py:398-439`); `_resolve_with_override` = body of
`_lookup_factor_id_with_override` (`:442-499`), docstrings updated to drop
"primary_factor_id" wording. Keep each function ≤40 lines.

- [x] **Step 1.4: Run the new tests until green**

```bash
cd backend && uv run pytest tests/unit/services/test_factor_resolver.py -x -q
```

- [x] **Step 1.5: Lint + type-check + commit**

```bash
cd backend && uv run ruff check app tests && uv run mypy app
git add backend/app/services/factor_resolver.py backend/tests/unit/services/test_factor_resolver.py
git commit -m "feat(1661): add FactorResolver for on-demand factor resolution"
```

---

### Task 2: emission compute resolves dynamically (`prepare_create`)

**Files:**
- Modify: `backend/app/services/data_entry_emission_service.py:230-322`
- Test: `backend/tests/unit/services/test_data_entry_emission_service.py`

**Interfaces:**
- Consumes: `FactorResolver.resolve` (Task 1).
- Produces: `prepare_create(..., factor_resolver: FactorResolver | None = None)`;
  `ctx["primary_factor_id"]` becomes a **computed, never-persisted** ctx key
  (all Strategy-A `resolve_computations` overrides keep reading it
  unchanged: `schemas/data_entry.py:356`, `modules/{purchase,buildings,
  equipment,process_emissions,external_cloud_and_ai,research_facilities}`).
- `_get_building_energy_type(factor: Factor | None) -> str | None`
  (signature change: takes the resolved factor, no id/cache deref).

- [ ] **Step 2.1: Write/adjust failing unit tests**

In `test_data_entry_emission_service.py` add:
- `test_prepare_create_resolves_factor_from_classification`: entry whose
  `data` contains kind/subkind but **no** `primary_factor_id`; patched
  resolver returns a factor; assert produced emission rows carry
  `primary_factor_id == factor.id`.
- `test_prepare_create_ignores_stale_stored_id`: entry `data` contains
  `primary_factor_id: 999` (legacy row) and classification resolving to
  factor id 7; assert emissions use 7, never 999.
- `test_building_energy_type_from_resolved_factor`: building entry; resolver
  returns factor with `classification["energy_type"] = "electric"`; assert
  only the electric heating leaf is produced (mirror the existing #1575
  tests, minus the stored id).

- [ ] **Step 2.2: Run, verify failing**

```bash
cd backend && uv run pytest tests/unit/services/test_data_entry_emission_service.py -x -q
```

- [ ] **Step 2.3: Implement**

In `prepare_create` (current code `data_entry_emission_service.py:264-322`):

1. Add parameter `factor_resolver: FactorResolver | None = None`; first line
   of body: `resolver = factor_resolver or FactorResolver(self.session)`.
2. **Reorder**: move the year-determination block (currently `:372-397`)
   *above* emission-type resolution — factor resolution needs `year`.
   Keep the `report` variable handling intact (percentage override below
   still uses it).
3. Move `handler = BaseModuleHandler.get_by_type(...)` (currently `:333`)
   up, next to the guards.
4. Resolve the primary factor once:

```python
primary_factor: Factor | None = None
if year is not None and handler.kind_field is not None:
    primary_factor = await resolver.resolve(
        handler, data_entry.data, DataEntryTypeEnum(data_entry.data_entry_type), year
    )
```

   (Strategy-B handlers such as plane have `kind_field` set but the value is
   not in `entry.data` → `resolve` returns `None`; their overridden
   `resolve_computations` never reads the ctx key. Same gate effect as the
   old `entry_kind_field in entry.data` check.)
5. Replace the `_get_building_energy_type` call (`:313-317`) with
   `building_energy_type = await self._get_building_energy_type(primary_factor)`
   and change that method (`:230-262`) to take `factor: Factor | None`:
   `None → None`; factor present but `classification.get("energy_type")`
   not in `BUILDING_ENERGY_TYPES` → raise `ValueError` (keep the loud-fail
   message, reworded without "references factor id"). Delete the
   `factor_cache`/`FactorService.get` deref — the resolver already returned
   the row.
6. In the ctx build (`:359`):

```python
ctx: dict = {**data_entry.data}
ctx.pop(KG_CO2EQ_OVERRIDE_KEY, None)
# Legacy rows may still carry a stored primary_factor_id — the resolver
# result always wins; the stored value is dead weight.
ctx["primary_factor_id"] = primary_factor.id if primary_factor else None
```

7. Keep `factor_cache`/`factor_query_cache` parameters as-is
   (`_fetch_factors` still uses them; recalc supplies them in Task 3).

- [ ] **Step 2.4: Tests green**

```bash
cd backend && uv run pytest tests/unit/services/test_data_entry_emission_service.py tests/unit/modules -q
```

- [ ] **Step 2.5: Lint + type-check + commit**

```bash
git commit -m "feat(1661): prepare_create resolves primary factor dynamically"
```

---

### Task 3: recalc workflow drops the rematch machinery

**Files:**
- Modify: `backend/app/workflows/emission_recalculation.py` (delete `:93-165`
  lookup building, `:192-262` rematch block, `:397-500` static helpers)
- Test: `backend/tests/unit/workflows/test_emission_recalculation.py`

**Interfaces:**
- Consumes: `FactorResolver` (Task 1), `prepare_create(factor_resolver=...)`
  (Task 2).

- [ ] **Step 3.1: Update unit tests first**

In `test_emission_recalculation.py`: delete the `_lookup_factor_id*` test
classes (their cases were ported to `test_factor_resolver.py` in Task 1 —
verify nothing was dropped by diffing case names). Rewrite rematch-behavior
tests as behavioral: after a factor swap, recalculated emissions carry the
new factor id **in the emission rows** (`DataEntryEmission.primary_factor_id`),
and `entry.data` is never mutated (assert `entry.data` unchanged
before/after the slice).

- [ ] **Step 3.2: Implement**

1. Replace lines `:105-165` (`factor_lookup`/`override_lookup`/`kind_lookup`
   construction) and the `list_by_data_entry_type` + `factor_cache` block with:

```python
resolver = FactorResolver(self.session)
factor_cache = await resolver.factors_by_id(data_entry_type_id, year)
factor_query_cache: dict = {}
```

2. Delete the whole per-entry rematch block (`:192-262`, the
   `entry_kind_field` locals, `entry.data` swap and its comments). The loop
   body becomes: validate → `prepare_create(entry_response, year=year,
   factor_cache=factor_cache, factor_query_cache=factor_query_cache,
   slice_cache=slice_cache, factor_resolver=resolver)` → buffer results.
   Keep the `seg` profile dict but drop the `"rematch"` key.
3. Delete `_lookup_factor_id` and `_lookup_factor_id_with_override`
   (`:397-500`) — now dead code (moved to the resolver in Task 1).
4. Remove now-unused imports (`FactorRepository` if only used for the
   deleted prefetch — check; the strict-drop contract note moves to the
   resolver docstring).

- [ ] **Step 3.3: Tests green**

```bash
cd backend && uv run pytest tests/unit/workflows/test_emission_recalculation.py -x -q
```

- [ ] **Step 3.4: Lint + type-check + commit**

```bash
git commit -m "refactor(1661): recalc uses FactorResolver, drop rematch machinery"
```

---

### Task 4: create/update paths stop stamping (`ModuleHandlerService`)

**Files:**
- Modify: `backend/app/services/module_handler_service.py`
- Modify: `backend/app/workflows/carbon_report_module.py:51-53,179-186`
- Test: `backend/tests/unit/services/test_module_handler_service.py`,
  `backend/tests/unit/workflows/test_carbon_report_module_update.py`

**Interfaces (produced):**

```python
class ModuleHandlerService:
    async def resolve_factor(
        self,
        handler: "ModuleHandler",
        payload: dict,
        data_entry_type_id: DataEntryTypeEnum,
        year: int,
        existing_data: Optional[dict] = None,
    ) -> Optional[Factor]: ...          # no payload mutation, returns match

    async def populate_defaults(
        self, handler: "ModuleHandler", data: dict, factor: Factor
    ) -> dict: ...                       # drops the stored-id guard

    async def resolve_factor_if_changed(
        self, handler, update_payload, data_entry_type, item_data,
        existing_data, year,
    ) -> tuple[dict, Optional[Factor]]: ...  # keeps clearing side-effects only
```

- [ ] **Step 4.1: Update unit tests first**

- Stamping asserts (`payload["primary_factor_id"] == …`) become return-value
  asserts (`factor.id == …`).
- New: `test_resolve_factor_does_not_mutate_payload`.
- `resolve_factor_if_changed`: keep the kind-change side-effect tests
  (subkind cleared, override code cleared) but assert **no**
  `primary_factor_id` key is written.
- `populate_defaults`: drop the id-mismatch-guard case; defaults apply
  whenever a factor is passed.

- [ ] **Step 4.2: Implement `module_handler_service.py`**

1. Rename `resolve_primary_factor_id` → `resolve_factor`; delete
   `payload["primary_factor_id"] = factor_id` (`:71`) and return only the
   factor. Internally replace `_resolve_by_classification` /
   `_resolve_with_kind_override` / `_match_by_override` (`:74-190`) with a
   single call to `FactorResolver(self.session).resolve(handler, data,
   data_entry_type_id, year)` — those three methods and the
   `factor_service.get_by_classification` dependency here become **dead
   code; delete them**. (Behavior note, from the spec: for override
   handlers the old code returned `factor=None`; the resolver returns the
   full `Factor`. `populate_defaults` is a no-op for handlers without
   `factor_value_fields`, so this only *adds* defaults where the module
   declares them — verify with the purchase tests.)
2. `populate_defaults` (`:192-214`): remove the
   `data.get("primary_factor_id") == factor.id` guard; keep the
   `factor_value_fields` loop.
3. Rename `resolve_primary_factor_if_changed` → `resolve_factor_if_changed`;
   delete `update_payload["primary_factor_id"] = None` (`:257`); the inner
   call becomes `factor = await self.resolve_factor(handler, update_payload,
   data_entry_type, year=year, existing_data=existing_data)` — the payload
   is returned unmodified except the kind-change clearing side-effects and
   `populate_defaults`.

- [ ] **Step 4.3: Implement `carbon_report_module.py`**

1. `create` (`:51-53`): **delete the resolve call entirely** — nothing in
   the create flow consumes the factor (emission compute resolves on its
   own in Task 2). Remove the now-unused `handler_service` local if nothing
   else uses it.
2. `update` (`:179-186`): call `resolve_factor_if_changed` (renamed); it
   still clears subkind/override on kind change and repopulates defaults.

- [ ] **Step 4.4: Tests green**

```bash
cd backend && uv run pytest tests/unit/services/test_module_handler_service.py \
  tests/unit/workflows/test_carbon_report_module_update.py -x -q
```

- [ ] **Step 4.5: Lint + type-check + commit**

```bash
git commit -m "refactor(1661): create/update resolve factors without stamping payloads"
```

---

### Task 5: CSV entry ingest stops stamping

**Files:**
- Modify: `backend/app/services/data_ingestion/base_csv_provider.py:1242-1280,1328-1334,1359-1366`
  and `_guard_factors_required` docstring (`:120-154`)
- Test: `backend/tests/unit/services/data_ingestion/test_base_csv_provider.py`,
  `backend/tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py`

- [ ] **Step 5.1: Update unit tests first** — asserts on
  `payload["primary_factor_id"]` / `data["primary_factor_id"]` become
  asserts that the key is **absent** from the built `DataEntry.data`, and
  that `populate_defaults` still fires when the factors_map matches.

- [ ] **Step 5.2: Implement**

1. In the row path (`:1242-1280`): keep the factors_map lookup (it feeds
   `populate_defaults` and the type/`require_factor_to_match` guards) but
   bind the matched **`Factor`** to a local `matched_factor` instead of
   extracting `primary_factor_id`.
2. Delete `payload["primary_factor_id"] = primary_factor_id` (`:1334`) and
   the stale comment above it (`:1328-1329`).
3. Simplify the populate block (`:1359-1366`):

```python
with self._timed("populate"):
    if matched_factor is not None:
        handler_service = ModuleHandlerService(self.data_session)
        data = await handler_service.populate_defaults(
            handler, data, matched_factor
        )
```

   (The `factor_id_to_factor` indirection in `setup_result` becomes unused
   here — grep `factor_id_to_factor`; if this was its only consumer, delete
   its construction too.)
4. `_guard_factors_required` docstring: reword "to populate
   primary_factor_id" → "to compute its emission".
5. `module_per_year.py`: comments only (`:21,28,90`) — the "no matching
   factor" *type-inference* error at `:212-219` is independent and stays.

- [ ] **Step 5.3: Tests green**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion -x -q
```

- [ ] **Step 5.4: Lint + type-check + commit**

```bash
git commit -m "refactor(1661): CSV ingest stops persisting primary_factor_id"
```

---

### Task 6: API layer — enrichment fallback, response DTO, export scrub

**Files:**
- Modify: `backend/app/repositories/data_entry_repo.py:786-795`
- Modify: `backend/app/repositories/carbon_report_module_repo.py:1236-1238`
- Modify: `backend/app/modules/equipment/schemas.py:98` (delete field)
- Modify: `frontend/src/types/api/openapi.d.ts` (regenerated)
- Test: `backend/tests/unit/repositories/test_data_entry_repo.py`

- [ ] **Step 6.1: Update tests first** — enrichment fallback test: entry
  with classification but no emission rows gets `primary_factor` populated
  from the resolver (patch `FactorResolver.resolve`); entry with a legacy
  `data["primary_factor_id"]` pointing at a *deleted* factor no longer
  500s/dereferences — the resolver result wins.

- [ ] **Step 6.2: Implement**

1. `data_entry_repo.py:786-795` — replace the id-deref fallback with the
   resolver (one `FactorResolver` instantiated before the row loop; the
   per-(det, year) memo makes per-row calls cheap):

```python
# No emission row carried a factor — derive it from the entry's
# classification (the entry never stores a factor id).
if primary_factor is None and data_entry.year is not None:
    primary_factor = await resolver.resolve(
        handler,
        data_entry.data,
        DataEntryTypeEnum(data_entry.data_entry_type_id),
        data_entry.year,
    )
```

   (`handler` is already in scope at `:783`. Verify `data_entry.year` is the
   denormalized column added for per-year deletes; if a row predates it,
   `None` → skip, same as today's missing-id behavior.)
2. Delete the export scrub in `carbon_report_module_repo.py:1236-1238`
   (`data.pop("primary_factor_id", None)` and its comment; keep the
   `.copy()` only if something else mutates — read the surrounding lines,
   otherwise drop the copy too).
3. Delete `primary_factor_id: Optional[int] = None` from
   `EquipmentHandlerResponse` (`modules/equipment/schemas.py:98`). Check the
   sort/filter maps in the same file (`:160` comment) — the NULL-sort
   comment about CSV rows becomes wrong; reword to reference emission-row
   factor ids.
4. Regenerate the frontend types:

```bash
make -C frontend gen-api-types
```

   Commit the regenerated `openapi.d.ts` (backend must be running for the
   schema fetch — see the target's recipe; start it the way the Makefile
   expects).

- [ ] **Step 6.3: Tests green**

```bash
cd backend && uv run pytest tests/unit/repositories -x -q
```

- [ ] **Step 6.4: Frontend type-check** (husky runs vue-tsc on commit; run it
  explicitly, `rtk tsc` green is NOT sufficient):

```bash
make -C frontend type-check
```

- [ ] **Step 6.5: Lint + commit**

```bash
git commit -m "refactor(1661): derive primary_factor in responses, drop stored-id fallback"
```

---

### Task 7: dead-code sweep + docstrings

**Files:** repo-wide grep; expected touchpoints listed below.

- [ ] **Step 7.1: Sweep**

```bash
cd backend && grep -rn "primary_factor_id" app --include="*.py" | grep -v __pycache__
```

Legitimate survivors — everything else must be gone or is a bug in Tasks 1-6:

- `app/models/data_entry_emission.py` — the FK column + docstrings.
- `app/repositories/data_entry_emission_repo.py` — column SQL.
- `app/repositories/data_entry_repo.py` — emission-column joins
  (`:539,580,591,619`).
- `app/seed/random_generator/*` — emission-table staging/FK DDL.
- `app/services/data_entry_emission_service.py` — writes to the emission
  **rows** (`primary_factor_id=factor.id` / `None`) and the ctx key.
- Strategy-A `resolve_computations` readers of `ctx["primary_factor_id"]`
  (base + module schemas).

- [ ] **Step 7.2: Docstring/comment fixes**

- `factor_repo.upsert_factors` docstring (`:151-155`): id preservation is
  still wanted (emission FK churn + Phase-2 stale detection via
  `last_seen_job_id`), but delete the claim that `DataEntry.data` stores
  factor ids.
- `api/v1/factors.py` `/stale` endpoint docstring (`:41-45`): same claim —
  reword to "historical: entries no longer store factor ids" or leave for
  deletion in Phase 2 (note it in the Progress log either way).
- `schemas/data_entry.py:343-356` docstring: "looks for primary_factor_id
  in *ctx* (Strategy A)" — still true; add "injected by
  DataEntryEmissionService.prepare_create from FactorResolver".
- Check `openapi.d.ts:878` comment disappears with regeneration.

- [ ] **Step 7.3: Full unit suite + lint + type-check**

```bash
cd backend && uv run pytest tests/unit -q && uv run ruff check app tests && uv run mypy app
```

- [ ] **Step 7.4: Commit**

```bash
git commit -m "chore(1661): dead-code sweep after primary_factor_id removal"
```

---

### Task 8: integration suite pass (Phase-1 gate)

- [ ] **Step 8.1: Run the integration suite** (PostgreSQL-backed; check
  `backend/Makefile` for the canonical target — the `*_pg.py` tests need it):

```bash
cd backend && uv run pytest tests/integration -q
```

- [ ] **Step 8.2: Fix fallout file-by-file.** Expected hot spots (all
  currently reference the stored id or the rematch path):

- `tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py`
  — retarget: reupload factors → recalc → **emission rows** carry new ids.
- `test_strategy_b_rematch_pg.py` — same shape.
- `test_plan_310b_factor_reupload_endpoint_pg.py`,
  `test_plan_310b_emission_change_pg.py` — drop stored-id assertions.
- `test_factor_lifecycle_pg.py`, `test_factor_upsert_copy_pg.py` — id
  preservation across reuploads still asserted (kept behavior).
- `test_purchase_factor_resolution_pg.py`, `test_headcount_pg.py`,
  `test_buildings_csv_pg.py`, `test_csv_ingest_matrix_pg.py`,
  `test_kg_co2eq_override_async_path_pg.py`,
  `test_recalc_source_uniformity_pg.py`, `test_stats_json_pg.py`,
  `test_travel_pg.py`, plane/equipment/train module tests — replace any
  `data["primary_factor_id"]` reads with emission-row assertions.
- `tests/conftest.py` — factories may stamp the key; remove.

Rule: assertions about *which factor was used* belong on
`DataEntryEmission.primary_factor_id`; assertions about *entry payloads*
must expect the key to be absent.

- [ ] **Step 8.3: Commit (possibly several small commits, one per test area)**

```bash
git commit -m "test(1661): retarget factor assertions to emission rows"
```

---

## Phase 2 — replace-semantics factor ingest (separate PR on top of Phase 1)

### Task 9: `delete_stale_for_year` repository method

**Files:**
- Modify: `backend/app/repositories/factor_repo.py` (next to
  `list_stale_for_year:360`)
- Test: `backend/tests/integration/services/data_ingestion/test_factor_replace_semantics_pg.py` (new)

**Interfaces:**

```python
async def delete_stale_for_year(self, year: int) -> int:
    """Delete factors superseded by the latest FACTORS ingest per det.

    Same staleness predicate as list_stale_for_year; returns rowcount.
    Emission rows referencing deleted factors are removed by the FK's
    ondelete=CASCADE and rebuilt by the enqueued recalc.
    """
```

- [ ] **Step 9.1: Failing integration test** — upload factors (job 1),
  reupload with one row dropped and one reshaped (job 2), call
  `delete_stale_for_year`, assert: dropped + old-shape rows gone, surviving
  ids preserved, emissions referencing deleted rows gone (CASCADE).
- [ ] **Step 9.2: Implement** — copy `list_stale_for_year`'s
  `latest_per_det`/`threshold` construction, issue a single
  `delete(Factor).where(...)` with the same conditions (wrap in `col()`),
  return `result.rowcount`.
- [ ] **Step 9.3: Green + commit** `feat(1661): add delete_stale_for_year`

### Task 10: wire deletion + recalc into factor ingest

**Files:**
- Modify: `backend/app/services/data_ingestion/base_factor_csv_provider.py`
  (post-upsert hook — find the `upsert_factors` call site)
- Test: extend `test_factor_replace_semantics_pg.py`; rerun
  `test_plan_310b_factor_reupload_endpoint_pg.py`

- [ ] **Step 10.1: Failing test** — end-to-end reupload through the provider:
  stale rows deleted, recalc enqueued (the 310C pipeline —
  `_enqueue_stale_recalculations` in `api/v1/data_sync.py:504` — is already
  triggered by the reupload endpoint; assert ordering: delete happens in the
  same transaction as the upsert, *before* the recalc job runs).
- [ ] **Step 10.2: Implement** — call `delete_stale_for_year(self.year)`
  right after a successful `upsert_factors` within the provider's
  transaction; log the deleted count into the job's stats/status message.
- [ ] **Step 10.3: The originating-bug regression test** (spec requirement):
  building_rooms factors uploaded with 2-key classification, reuploaded with
  3-key (`energy_type` added); assert old generation deleted,
  `GET /v1/factors/30/classes/{kind}/values?sub_class=...&year=...` returns
  200 with the new factor (was: 500 `MultipleResultsFound`).
- [ ] **Step 10.4: Green + commit** `feat(1661): factor reupload replaces stale rows`

### Task 11: remove the stale-factor surface

**Files:**
- Modify: `backend/app/api/v1/factors.py` (delete `/stale` route +
  `StaleFactorResponse`, `:18-71`)
- Modify: `backend/app/repositories/factor_repo.py` (delete
  `list_stale_for_year` + `_latest_factor_job_per_det` **if** Task 9 inlined
  its own copy — otherwise keep the shared helper and delete only the list
  method)
- Modify: frontend — grep `factors/stale` in `frontend/src`; remove the
  operator warning UI + API call; regenerate `openapi.d.ts`
  (`make -C frontend gen-api-types`)
- Test: delete the `/stale` endpoint tests; grep
  `list_stale_for_year|StaleFactorResponse` in `backend/tests`

- [ ] **Step 11.1: Implement + tests green**
- [ ] **Step 11.2: Frontend type-check** (`make -C frontend type-check`)
- [ ] **Step 11.3: Commit** `refactor(1661): remove stale-factor endpoint and flagging`

### Task 12: close out

- [ ] **Step 12.1:** Full backend suite + lint + type-check green (user runs
  or CI).
- [ ] **Step 12.2:** Update the spec (`1661-remove-primary-factor-id.md`) if
  anything shipped differently; set both files' `status:` frontmatter
  (`delivered` when merged).
- [ ] **Step 12.3:** PRs target `dev` unless told otherwise; Phase 1 and
  Phase 2 are separate PRs (`gh pr create --base dev`). No attribution
  trailers in PR bodies.

---

## Progress log

_Append one line per session: date, task/step reached, surprises._

- 2026-07-05: Plan written. No code started.
- 2026-07-05: Task 1 complete (FactorResolver + 16 tests, commits 99f1831a, 1c53a1f1; review approved after adding 2 ported test cases).
