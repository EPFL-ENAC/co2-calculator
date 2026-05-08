---
status: delivered
last_updated: 2026-05-04
title: "Stop persisting computed fields to DataEntry.data"
summary: "Stop persisting computed fields back into DataEntry.data; recompute on read instead. Single-PR refactor delivered during sprint 10; no tracking issue."
---

# Implementation Plan: Stop persisting computed fields to `DataEntry.data`

> **Scope decision**: single PR combining all changes below.
> **DB cleanup**: not in scope — DB will be dropped.

## 1. Diagnosis

`DataEntryRepository.get_submodule_data` (`backend/app/repositories/data_entry_repo.py:341`) runs a `select(...)` returning `DataEntry` ORM rows tied to the active `AsyncSession`. After unpacking each row at line 561, the loop reassigns `data_entry.data = {**data_entry.data, ...}` three times (lines 587, 602, 613). SQLAlchemy's attribute instrumentation marks the row dirty.

The mutation is persisted by:

- **Autoflush** — the `Factor` lookup at line 580 (executed inside the same loop) triggers a flush of the dirty `DataEntry`.
- **Explicit commit** — write workflows (`carbon_report_module.py:111`) reuse the same session and flush dirty rows.

A second source of leakage: CSV/API providers stuff a `kg_co2eq` override directly into `DataEntry.data` at ingest time, also persisting it.

Repo-wide grep (`data_entry\.data\s*=`) found:

- `repositories/data_entry_repo.py:120` — legitimate `update()`.
- `repositories/data_entry_repo.py:587, 602, 613` — the read-path bug.

No other read method mutates `.data`.

## 2. Option 1 — Don't touch the ORM in `to_response`

### Signature change

Protocol (`app/schemas/data_entry.py:131`):

```python
def to_response(
    self,
    data_entry: T,
    enriched_data: dict | None = None,
) -> DataEntryResponseGen: ...
```

Each implementation does:

```python
data = enriched_data if enriched_data is not None else data_entry.data
```

…and uses `data` in place of `data_entry.data` in the body.

In `get_submodule_data`, replace the three mutation blocks with a local `enriched_data` dict and pass it via `handler.to_response(data_entry, enriched_data)`. The ORM row is never touched.

### Files to edit

Repo:

- `backend/app/repositories/data_entry_repo.py` (mutations at 587–620 → local dict)

Protocol:

- `backend/app/schemas/data_entry.py:131`

Handler implementations (14 sites, 9 files):

- `backend/app/modules/buildings/schemas.py:249, 483, 599`
- `backend/app/modules/process_emissions/schemas.py:97`
- `backend/app/modules/external_cloud_and_ai/schemas.py:203, 385`
- `backend/app/modules/equipment_electric_consumption/schemas.py:227`
- `backend/app/modules/purchase/schemas.py:195, 296`
- `backend/app/modules/professional_travel/schemas.py:207`
- `backend/app/modules/research_facilities/animals_schemas.py:85`
- `backend/app/modules/research_facilities/common_schemas.py:101`
- `backend/app/modules/headcount/schemas.py:196, 251`

## 3. Option 2 — `expunge` defense

After unpacking each row, call `self.session.expunge(...)` on every ORM instance returned. This detaches the instances so any later mutation cannot trigger a flush.

Apply in `data_entry_repo.py` to:

- `get_submodule_data` (line 341)
- `get_list` (line 173)
- `list_by_data_entry_type_and_year` (line 195)
- `get_headcount_members` (line 778)
- `get_member_by_institutional_id` (line 808)

Add a private helper:

```python
def _detach(self, *objs: Any) -> None:
    for obj in objs:
        if obj is not None:
            self.session.expunge(obj)
```

Note: `get_submodule_data` only accesses scalar columns and the JSON `data` after unpack (no lazy relationships), so expunging is safe. Add a comment to that effect.

## 4. `kg_co2eq` must never be persisted in `DataEntry.data`

### Where it leaks in today

- `backend/app/services/data_ingestion/base_csv_provider.py:802-809` (special-case adds `kg_co2eq` into `filtered_row`); line 952 builds `DataEntry(data=...)` with that key still inside.
- `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py:416-422` (writes `kg_co2eq` into `data_payload`).
- `backend/app/services/data_entry_emission_service.py:182` (`prepare_create` reads `data_entry.data.get("kg_co2eq")` as the override).
- `backend/app/services/data_entry_emission_service.py:486-492` (`upsert_by_data_entry` workaround that strips `kg_co2eq` from the in-memory Pydantic copy before recompute — defensive, doesn't affect DB).

### New transient channel

Extend `prepare_create`:

```python
async def prepare_create(
    self,
    data_entry: DataEntry | DataEntryResponse,
    kg_co2eq_override: float | None = None,
) -> list[DataEntryEmission]:
    ...
    if kg_co2eq_override is not None:
        # CSV/API ingestion path: build override emission record
```

Drop the `data_entry.data.get("kg_co2eq")` fallback at line 182 — the override is now exclusively passed in.

### Provider changes

- **CSV provider** (`base_csv_provider.py`): in `_process_row`, extract `kg_co2eq` from `filtered_row` _before_ the `DataEntry(data=...)` build (line 952), keep it on a parallel structure (e.g. `data_entry._kg_co2eq_override` transient attribute, or zip alongside batch). Strip the key from `data` so the persisted row is clean. In `_persist_batch` (line 1126 region), pass `kg_co2eq_override=...` to `prepare_create`.

  Easiest carrier: add a private `_csv_overrides_by_idx: dict[int, float]` on the provider instance keyed by the index in the batch list, and look it up after `bulk_create` returns the response objects in batch order.

- **API provider** (`professional_travel_api_provider.py`): mirror the CSV provider — don't write `kg_co2eq` into `data_payload`; track it on a parallel mapping; pass to `prepare_create`.

### Remove the workaround

`upsert_by_data_entry` (`data_entry_emission_service.py:486-492`): delete the strip block. It exists only to defend against the read-path mutation; once Option 1 lands, it's dead code.

## 5. `EnergyCombustion` latent bug fix

`buildings/schemas.py:484-485`:

```python
primary_factor = data_entry.data.get("primary_factor", {})
factor_values = primary_factor.get("values", {})  # always {} — there is no nested "values"
```

The repo builds `primary_factor` as a flat `{**values, **classification}` dict. Fix the read site to use the flat shape:

```python
data = enriched_data if enriched_data is not None else data_entry.data
primary_factor = data.get("primary_factor", {})
# primary_factor is already flat (factor.values merged with factor.classification)
factor_values = primary_factor
```

(Or pick whichever shape makes the response_dto field mapping work — verify against `EnergyCombustionHandlerResponse` field names.)

> ⚠️ **PR-description note (frontend-visible behavior change)**:
> Today, `factor_values = primary_factor.get("values", {})` always returns `{}`,
> so the response fields `name` (and `unit` via the same path) are derived
> only from `data_entry.data.get("name") / get("unit")` — and were `None`
> on most rows. After the fix, `name`/`unit` will start populating from the
> factor's `kind` / `unit` classification when those exist on the matched
> factor. The frontend's energy combustion submodule listing will start
> showing those values. Manual UI verification recommended (the user has
> agreed to check this manually).

## 6. Tests

### Repo regression — read path doesn't pollute `data`

`backend/tests/unit/repositories/test_data_entry_repo.py`:

```python
@pytest.mark.asyncio
async def test_get_submodule_data_does_not_persist_computed_fields(
    db_session: AsyncSession,
):
    """Listing must not write computed fields back to DataEntry.data."""
    # arrange: build a plane DataEntry with input-only data
    # act: call get_submodule_data, then commit
    # assert: refreshed row's `data` matches original input exactly
```

The test should fail today and pass after Options 1 & 2.

Add an analogous test for `is_buildings_entry` (asserts `room_surface_square_meter` is absent unless it was in the original input).

### CSV regression — `kg_co2eq` only in emission, not in `data`

Per-year and per-module fixtures. Module coverage: every CSV-importable module that may carry a `kg_co2eq` column. Concretely, professional_travel (plane/train), buildings (energy_combustion, building_room), purchase, equipment, external_cloud_and_ai, headcount.

For each fixture:

1. Run the CSV importer.
2. Query `data_entries` and assert no row has `kg_co2eq` key in `data`.
3. Query `data_entry_emissions` and assert at least one row has the expected `kg_co2eq` value.
4. Run a recompute (e.g. update the parent module) and assert the emission's `kg_co2eq` is recomputed via formula (not via the stripped CSV value) when there's no override on file.

Fixture location: `backend/tests/fixtures/csv/regression_kg_co2eq/<year>/<module>.csv` (dumb 2–3 row files).

### API-provider regression

Mirror the CSV test for the professional-travel API provider — feed it a synthetic API response with `OUT_CO2_CORRECTED`, assert the persisted `DataEntry.data` has no `kg_co2eq` key and `DataEntryEmission.kg_co2eq` matches the API value.

### Unit test — `prepare_create(kg_co2eq_override=...)`

Direct unit test on `DataEntryEmissionService.prepare_create`:

- Given a `DataEntry` whose `data` does NOT contain `kg_co2eq`, calling with `kg_co2eq_override=42.0` returns an emission with `kg_co2eq=42.0`.
- Without the override, the formula path runs.

## 7. Risks

- **`kg_co2eq_override` override semantics**: the existing override path skipped factor-based formula computation entirely. After the refactor, that semantic must hold — the new `kg_co2eq_override` param must produce the same single-emission row with `primary_factor_id=None`.
- **`EnergyCombustion` shape fix**: ensure response_dto fields still resolve. The latent bug means consumers were getting `{}` for `factor_values`; verify the response_dto doesn't depend on a `values`-keyed sub-dict.
- **API provider parity**: ensure the same override path works in the API provider's call to `bulk_create` + `prepare_create` (verify it uses the same emission_service surface).

## 8. Implementation order (single PR)

1. Add `kg_co2eq_override` param to `prepare_create`; remove `data.get("kg_co2eq")` fallback. Update unit tests.
2. Update CSV provider to strip `kg_co2eq` from `data` and pass override transiently.
3. Update API provider similarly.
4. Remove workaround strip in `upsert_by_data_entry`.
5. Change `to_response` protocol + 14 implementations (Option 1).
6. Build `enriched_data` in `get_submodule_data`; remove ORM mutations.
7. Add `_detach`/`session.expunge` to the 5 read methods (Option 2).
8. Fix `EnergyCombustion` latent bug.
9. Add regression tests (repo + CSV fixtures + API + prepare_create unit).
10. Run full test suite.

## Critical files

- `backend/app/repositories/data_entry_repo.py`
- `backend/app/schemas/data_entry.py`
- `backend/app/services/data_entry_emission_service.py`
- `backend/app/services/data_ingestion/base_csv_provider.py`
- `backend/app/services/data_ingestion/api_providers/professional_travel_api_provider.py`
- `backend/app/modules/buildings/schemas.py`
- `backend/app/modules/professional_travel/schemas.py`
- `backend/app/modules/process_emissions/schemas.py`
- `backend/app/modules/external_cloud_and_ai/schemas.py`
- `backend/app/modules/equipment_electric_consumption/schemas.py`
- `backend/app/modules/purchase/schemas.py`
- `backend/app/modules/research_facilities/animals_schemas.py`
- `backend/app/modules/research_facilities/common_schemas.py`
- `backend/app/modules/headcount/schemas.py`
- `backend/tests/unit/repositories/test_data_entry_repo.py`
- `backend/tests/fixtures/csv/regression_kg_co2eq/...`
