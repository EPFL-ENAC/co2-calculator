---
status: delivered
issue: 859
last_updated: 2026-05-06
title: "Refactor Seed Factors to Use Ingestion Machinery"
summary: "Replace duplicated factor-seed parsing with a LocalFactorCSVProvider that reuses the ingestion pipeline."
---

## Plan: Refactor Seed Factors to Use Ingestion Machinery

**TL;DR**: `seed_generic_factors.py` manually duplicates CSV parsing, handler resolution, and factor creation logic that already exists in `ModulePerYearFactorCSVProvider`. The refactoring introduces a thin `LocalFactorCSVProvider` subclass that bypasses file-store/job-tracking (API-only concerns) and rewrites `seed_factors()` to delegate to it.

---

### Phase 1 — Add deletion hook to `BaseFactorCSVProvider` _(small, non-breaking)_

**File**: base_factor_csv_provider.py

- Extract the `data_entry_type_to_iterates` block in `process_csv_in_batches` into a new overridable method `_get_types_to_delete(listed_entry_types)`.
- This is needed because `purchases_common_factors.csv` covers **7 of 8** purchase types; module-type-based deletion would also erase `additional_purchases` factors seeded just before it. Scoping deletion to the explicit configured types preserves the current behavior.

### Phase 2 — Create `LocalFactorCSVProvider` _(new file)_

**New file**: `app/services/data_ingestion/csv_providers/local_seed.py`

Extends `ModulePerYearFactorCSVProvider`. Config keys:

| Key                       | Value                                                                         |
| ------------------------- | ----------------------------------------------------------------------------- |
| `local_file_path`         | absolute path to seed CSV on disk                                             |
| `module_type_id`          | derived via `get_module_type_for_data_entry_type(config.data_entry_types[0])` |
| `data_entry_type_id`      | `data_entry_types[0].value` if no `data_entry_type_column`, else `None`       |
| `year`                    | `2025` (same default)                                                         |
| `explicit_entry_type_ids` | `[det.value for det in config.data_entry_types]` — scopes deletion            |

Override 4 methods:

1. `validate_connection()` — check local file exists (no file store)
2. `_setup_and_validate()` — read CSV bytes from disk; skip file-store move + job DB updates; return `setup_result` with `csv_text` + handler info
3. `_finalize_and_commit()` — skip file-store moves + job DB updates; just process last batch + flush session
4. `_get_types_to_delete()` — return `explicit_entry_type_ids` when provided; else `super()`

### Phase 3 — Refactor `seed_generic_factors.py`

**File**: seed_generic_factors.py

- Replace `seed_factors()` body: derive `module_type_id` and `data_entry_type_id` from `FactorSeedConfig`, instantiate `LocalFactorCSVProvider`, call `provider.process_csv_in_batches()`, print stats.
- Remove: `get_float_str_or_none()`, manual classification/value extraction (both replaced by the provider's `_process_row` + `_convert_value`).
- Keep: `FactorSeedConfig` dataclass, `FACTOR_SEEDS` list, `main()` — no external interface changes.

---

### Relevant Files

- seed_generic_factors.py — main file to refactor
- base_factor_csv_provider.py — add `_get_types_to_delete` hook
- factors.py — `ModulePerYearFactorCSVProvider` to subclass
- app/services/data_ingestion/csv_providers/local_seed.py — new file
- module_type.py — `get_module_type_for_data_entry_type` to derive `module_type_id`

### Verification

1. `uv run pytest tests/ -k "factor" -v` — existing tests pass
2. `uv run python -m app.seed.seed_generic_factors` — run refactored seed; check output stats match expected counts
3. `make lint && make type-check`

---

### Decisions

- **Approach chosen**: thin subclass adapter (`LocalFactorCSVProvider`) — only adds a small hook to the base class, leaves the production ingestion path untouched.
- **Alternative rejected**: uploading local CSVs to file store + creating `DataIngestionJob` records — adds DB/storage overhead and requires the file store operational during seeding.
- `LocalFactorCSVProvider` lives in `csv_providers/` alongside the other provider implementations.
- No `DataIngestionJob` creation — seeds have no job tracking.
- Year remains hardcoded `2025` in the seed.
