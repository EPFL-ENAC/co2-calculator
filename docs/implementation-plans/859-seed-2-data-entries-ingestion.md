# Plan: Refactor `seed_generic_data_entries` to Use Ingestion Machinery

## TL;DR

`seed_generic_data_entries.py` manually parses CSV rows, resolves factors, resolves locations, builds `DataEntry` objects, then calls emission services directly. The app already has `ModulePerYearCSVProvider` that does all of this with batching, deduplication, error tracking, and stats recomputation. Add `LocalDataEntryCSVProvider` to the existing `local_seed.py` file — it bypasses file-store/job-DB operations while reusing the full row-processing pipeline. Then simplify `seed_data_entries()` to just instantiate the provider and call `process_csv_in_batches()`.

## Key Architecture Insights

- `_setup_handlers_and_factors()` and `_resolve_handler_and_validate()` read `self.job.module_type_id` — solved by setting `self.job = SimpleNamespace(module_type_id=..., data_entry_type_id=...)` (not persisted)
- `_update_job()` is a no-op when `job_id is None` — already guarded
- `_delete_existing_entries_for_module_per_year()` only deletes `source=CSV_MODULE_PER_YEAR` entries (better than original which deleted all)
- Deletion scope controlled by `self.job.data_entry_type_id`: set to single type for single-type CSVs, `None` for multi-type (deletes all module types)
- `_recompute_module_stats()` uses `self._unit_to_module_map` set in `process_csv_in_batches()` before our overridden `_finalize_and_commit` is called
- Location fields (travel CSVs): base `_process_row` filters row to `expected_columns` — IATA codes get discarded. Solution: pre-build location cache in `_setup_and_validate()`, override `_process_row()` to inject IDs before calling super

## Steps

### Step 1 — Add `LocalDataEntryCSVProvider` to `local_seed.py`

**File**: `app/services/data_ingestion/csv_providers/local_seed.py`

Update the module docstring and add these imports:
- `csv as csv_module`, `io`
- `from types import SimpleNamespace`
- `from sqlalchemy import select`, `from sqlmodel import col`
- `from app.models.data_entry import DataEntry, DataEntryTypeEnum`
- `from app.models.location import Location, TransportModeEnum`
- `from app.services.data_ingestion.base_csv_provider import StatsDict`
- `from app.services.data_ingestion.csv_providers.module_per_year import ModulePerYearCSVProvider`
- `from app.services.data_entry_emission_service import DataEntryEmissionService`
- `from app.services.data_entry_service import DataEntryService`

Config keys for `LocalDataEntryCSVProvider`:

| Key | Type | Value from seed config |
|---|---|---|
| `local_file_path` | `str` | `str(config.path)` |
| `module_type_id` | `int` | `config.module_type.value` |
| `data_entry_type_id` | `int \| None` | `types[0].value` if single type, else `None` |
| `year` | `int` | `YEAR` (2025) |
| `location_fields` | `dict[str,str] \| None` | `config.location_fields` |
| `transport_mode_value` | `str \| None` | `config.transport_mode.value` if set |

Override 4 methods:

**`__init__`**: call super with `user=None, job_session=None`; set `self.job = SimpleNamespace(module_type_id=..., data_entry_type_id=...)`; store `_local_file_path`, `_location_fields`, `_transport_mode`

**`validate_connection()`**: `return Path(self._local_file_path).is_file()`

**`_setup_and_validate()`**:
1. Read CSV from disk with `utf-8-sig` encoding
2. If `_location_fields and _transport_mode`: call async `_build_location_cache(csv_text)`
3. Call `await self._setup_handlers_and_factors()`
4. Call `await self._validate_csv_headers(...)` (`async` method in BaseCSVProvider)
5. Return same keys as parent + `"location_id_cache"` + `"processing_path": None` (dummy)

**`_build_location_cache(csv_text)`** (new private async method):
- Scan CSV for unique codes in source columns
- Planes: `SELECT ... WHERE iata_code IN (...) AND transport_mode = plane` → `{code.upper(): id}`
- Trains: load all train locations → match `{name.lower(): id}` against codes
- Log warning for unresolved codes

**`_process_row(row, row_idx, setup_result, stats, max_row_errors, unit_to_module_map)`**:
- If `_location_fields`: shallow-copy row; look up each source column in `setup_result["location_id_cache"]`; inject `data_key: str(loc_id)` (skip if `None`)
- Call `super()._process_row(modified_row, ...)`

**`_finalize_and_commit(batch, data_entry_service, emission_service, stats, setup_result)`**:
- Process final batch, increment `stats["batches_processed"]`
- `await self.data_session.flush()`
- `await self._recompute_module_stats()`
- Return `{"state": "FINISHED", "result": ..., "inserted": ..., "skipped": ..., "stats": ...}`

### Step 2 — Refactor `seed_generic_data_entries.py`

**File**: `app/seed/seed_generic_data_entries.py`

Replace `seed_data_entries()` body to use `LocalDataEntryCSVProvider`.

Remove imports: `csv`, `get_args`, `BaseModel`, `sqlalchemy.select`, `sqlmodel.col`, `BaseModuleHandler`, `get_carbon_report_module_id/load_factors_map/lookup_factor`, `CarbonReportModuleService`, `DataEntryEmissionService`, `DataEntryService`, `DataEntry`

Remove functions: `_get_string_field_names`, `_coerce_value`, `_resolve_location_id`, `_resolve_type_from_factors`

Add import: `from app.services.data_ingestion.csv_providers.local_seed import LocalDataEntryCSVProvider`

Keep unchanged: `EXCLUDE_COLUMNS`, `SEED_FOLDER`, `YEAR`, `DataEntrySeedConfig`, `DATA_ENTRY_SEEDS`, `main()`

New `seed_data_entries()`:
```python
async def seed_data_entries(session: AsyncSession, config: DataEntrySeedConfig) -> None:
    if not config.path.exists():
        logger.warning("CSV not found, skipping: %s", config.path)
        return
    provider_config = {
        "local_file_path": str(config.path),
        "module_type_id": config.module_type.value,
        "year": YEAR,
        "data_entry_type_id": config.data_entry_types[0].value if len(config.data_entry_types) == 1 else None,
        "location_fields": config.location_fields,
        "transport_mode_value": config.transport_mode.value if config.transport_mode else None,
    }
    provider = LocalDataEntryCSVProvider(config=provider_config, data_session=session)
    result = await provider.process_csv_in_batches()
    label = ", ".join(det.name for det in config.data_entry_types)
    print(f"Created {result['inserted']} entries for [{label}] ({result['skipped']} skipped)")
    await session.commit()
    logger.info("Seeded data entries for [%s].", label)
```

## Relevant Files

- `app/seed/seed_generic_data_entries.py` — refactor `seed_data_entries()` and imports
- `app/services/data_ingestion/csv_providers/local_seed.py` — add `LocalDataEntryCSVProvider` after `LocalFactorCSVProvider`
- `app/services/data_ingestion/base_csv_provider.py` — reference: `StatsDict`, `_validate_csv_headers` (async!), `_delete_existing_entries_for_module_per_year`
- `app/services/data_ingestion/csv_providers/module_per_year.py` — base class: `ModulePerYearCSVProvider`
- `app/models/location.py` — `Location`, `TransportModeEnum`

## Verification

1. `uv run pytest tests/ -k "data_entry or ingestion" -v` — existing tests pass
2. `uv run python -m app.seed.seed_generic_data_entries` — check output counts match expected
3. `make lint && make type-check`

## Decisions

- **No new hook on `base_csv_provider.py`**: deletion scope is already controlled by `self.job.data_entry_type_id`; the mock `SimpleNamespace` job handles it correctly
- **`SimpleNamespace` mock job**: not added to any session, never persisted; safe for attributes `module_type_id` and `data_entry_type_id`
- **Deletion behavior change**: ingestion only deletes `CSV_MODULE_PER_YEAR` entries (original deleted all). For fresh-DB seeding these are equivalent; for re-seeding, this is better (preserves manual entries)
- `LocalDataEntryCSVProvider` lives in `local_seed.py` alongside `LocalFactorCSVProvider`
