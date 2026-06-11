# CSV Provider Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** planned
**Spun out of:** #1458 review (equipment kg_co2eq ingestion work)

**Goal:** Eliminate the copy-paste duplication between `ModuleUnitSpecificCSVProvider` and `ModulePerYearCSVProvider` by hoisting the shared logic into `BaseCSVProvider`, converging the behaviors that have accidentally forked.

**Architecture:** `BaseCSVProvider` already uses the template-method pattern, but its abstract hooks are cut too wide — each subclass reimplements whole steps instead of just its variant. This plan narrows the hooks: the base gains three concrete helpers (`_load_handlers_and_factors`, `_assemble_setup_result`, `_resolve_type_from_config_or_category`) and a concrete default `_extract_kind_subkind_values`. The two providers shrink to their genuine deltas: where the target module comes from, whether the data_entry_type may be inferred from factors, and how strict column validation is.

**Tech Stack:** Python 3.12, FastAPI backend, pytest (`uv run pytest`), mypy (`make type-check`), ruff (`make lint`). All commands run from `backend/`.

---

## Behavioral decisions (agreed with maintainer — do not re-litigate)

| Divergence today                                                                                                                                  | Converged behavior                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `module_unit_specific.py` casts `int(data_entry_type_id)`; `module_per_year.py` does not                                                          | **Both cast** `DataEntryTypeEnum(int(...))` — string ids from job config must work in both                                                                                   |
| `module_unit_specific` rejects rows early via `is_in_factors_map` + `require_factor_to_match`; `module_per_year` defers to `ModuleHandlerService` | **Match module_per_year**: drop the early per-row factor-match rejection from unit_specific entirely. `ModuleHandlerService` handles factor validation during row processing |
| `module_unit_specific` requires `year` at setup; `module_per_year` only checks it in `_resolve_carbon_report_modules`                             | **Both require year at setup** (in the shared loader). The factor lookup keys on `{type}:{year}:{kind}:{subkind}`, so a missing year silently misses every factor            |
| `_extract_kind_subkind_values`: unit_specific = single-handler only; per_year = handler fields + `kind`/`Kind`/`KIND` fallback                    | **per_year's implementation becomes the base default**; both subclass overrides are deleted (single-handler is just the n=1 case)                                            |
| `required_columns`: derived from handler vs hardcoded `{"unit_institutional_id"}`                                                                 | **Stays a per-provider decision**, passed as an argument to the shared assembler (this is a genuine difference, not drift)                                                   |

## Files

- Modify: `backend/app/services/data_ingestion/base_csv_provider.py`
- Modify: `backend/app/services/data_ingestion/csv_providers/module_per_year.py` (full rewrite, shrinks)
- Modify: `backend/app/services/data_ingestion/csv_providers/module_unit_specific.py` (full rewrite, shrinks)
- Modify: `backend/tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py`
- Modify: `backend/tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py`

**Key constraint on test monkeypatching:** today the tests patch `csv_providers_module.module_per_year.load_factors_map` (module-level function reference). After this refactor, `load_factors_map` is called from `base_csv_provider`, so those patches MUST be retargeted to the base module or they silently patch a dead reference. Patches of `BaseModuleHandler.get_by_type` mutate the class object itself, but `module_unit_specific` will no longer import `BaseModuleHandler` at all, so those attribute paths must also be retargeted.

---

### Task 1: Branch setup

- [ ] **Step 1: Create a branch off fresh dev**

```bash
git fetch origin
git checkout -b refactor/csv-provider-consolidation origin/dev
```

- [ ] **Step 2: Confirm the baseline is green**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/ -q
```

Expected: all tests pass. If not, STOP and report — do not build on a red baseline.

---

### Task 2: Add shared helpers to BaseCSVProvider

**Files:**

- Modify: `backend/app/services/data_ingestion/base_csv_provider.py`

This task is purely additive (plus making one abstract method concrete), so existing tests stay green. The new helpers are exercised through the providers in Tasks 3–4.

- [ ] **Step 1: Add imports**

In `base_csv_provider.py`, change the existing import

```python
from app.schemas.data_entry import DATA_ENTRY_META_FIELDS, ModuleHandler
```

to

```python
from app.schemas.data_entry import (
    DATA_ENTRY_META_FIELDS,
    BaseModuleHandler,
    ModuleHandler,
)
```

and add (alphabetically with the other `app.` imports):

```python
from app.seed.seed_helper import load_factors_map
```

Sanity check for circular imports: `app/seed/seed_helper.py` must not import `base_csv_provider` (it does not today — it only provides factor-map helpers). If the import fails at collection time, STOP and report.

- [ ] **Step 2: Replace the abstract `_extract_kind_subkind_values` with a concrete implementation**

In `base_csv_provider.py`, the class currently has (around line 329):

```python
    @abstractmethod
    def _extract_kind_subkind_values(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
    ) -> tuple[str, str | None]:
        """
        Extract kind and subkind values from filtered row.

        Subclasses implement entity-specific extraction logic
        (e.g., single handler vs. multiple handlers).

        Returns: (kind_value, subkind_value)
        """
        pass
```

Replace it with this concrete method (this is `ModulePerYearCSVProvider`'s current implementation, verbatim logic — it handles the single-handler case as n=1):

```python
    def _extract_kind_subkind_values(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
    ) -> tuple[str, str | None]:
        """
        Extract kind and subkind values from filtered row.

        Tries each handler's kind_field/subkind_field first, then falls
        back to common field names. Works for single- and multi-handler
        providers alike.

        Returns: (kind_value, subkind_value)
        """
        # Try to find kind/subkind using each handler's fields
        for handler in handlers:
            if handler.kind_field and handler.kind_field in filtered_row:
                kind_value = filtered_row.get(handler.kind_field, "")
                subkind_value = (
                    filtered_row.get(handler.subkind_field)
                    if handler.subkind_field
                    else None
                )
                return kind_value, subkind_value

        # Fallback: try common field names
        for handler in handlers:
            subkind_value = None
            if handler.subkind_field and handler.subkind_field in filtered_row:
                subkind_value = filtered_row.get(handler.subkind_field)

            for kind_field_name in ("kind", "Kind", "KIND"):
                if kind_field_name in filtered_row:
                    kind_value = filtered_row.get(kind_field_name, "")
                    return kind_value, subkind_value

        # Last resort: return empty if nothing found
        return "", None
```

- [ ] **Step 3: Add the three shared helpers**

In `base_csv_provider.py`, immediately after the abstract `_setup_handlers_and_factors` method, add:

```python
    async def _load_handlers_and_factors(
        self, entry_types: List[DataEntryTypeEnum]
    ) -> tuple[List[Any], Dict[str, Any]]:
        """
        Load deduplicated handlers and the merged factors map for the
        given data entry types.

        Year is required: factor lookups during row processing key on
        ``{type}:{year}:{kind}:{subkind}``, so a missing year would
        silently miss every factor and import rows with
        primary_factor_id=None.
        """
        if not self.year:
            raise ValueError(
                f"year is required for {self.entity_type.name} entity type"
            )

        # Deduplicate handlers by class to avoid multiple identical
        # instances (e.g., EquipmentModuleHandler registered for
        # it/scientific/other)
        handlers: List[Any] = []
        seen_handler_classes: set[type[Any]] = set()
        for entry_type in entry_types:
            handler = BaseModuleHandler.get_by_type(entry_type)
            handler_class: type[Any] = type(handler)
            if handler_class not in seen_handler_classes:
                handlers.append(handler)
                seen_handler_classes.add(handler_class)

        factors_map: Dict[str, Any] = {}
        for entry_type in entry_types:
            type_factors = await load_factors_map(
                self.data_session, entry_type, self.year
            )
            factors_map.update(type_factors)

        return handlers, factors_map

    def _assemble_setup_result(
        self,
        *,
        handlers: List[Any],
        factors_map: Dict[str, Any],
        module_label: str,
        required_columns: set[str],
    ) -> Dict[str, Any]:
        """
        Build the setup dict returned by ``_setup_handlers_and_factors``.

        Runs the require-factor guard, derives expected columns, and
        builds the factor_id -> factor map for O(1) lookup during row
        processing (avoids an O(n) scan of factors_map per row).
        """
        _guard_factors_required(
            factors_map=factors_map,
            handlers=handlers,
            module_label=module_label,
            year=self.year,
        )

        expected_columns = _get_expected_columns_from_handlers(handlers)

        factor_id_to_factor: Dict[int, Any] = {}
        for factor in factors_map.values():
            factor_id = getattr(factor, "id", None)
            if factor_id is not None:
                factor_id_to_factor[factor_id] = factor

        logger.info(
            f"Setup complete for {self.entity_type.name}: "
            f"handlers={len(handlers)}, "
            f"factors={len(factors_map)}, "
            f"factor_id_to_factor={len(factor_id_to_factor)}, "
            f"expected_columns={len(expected_columns)}, "
            f"required_columns={len(required_columns)}"
        )

        return {
            "handlers": handlers,
            "factors_map": factors_map,
            "factor_id_to_factor": factor_id_to_factor,
            "expected_columns": expected_columns,
            "required_columns": required_columns,
        }

    def _resolve_type_from_config_or_category(
        self,
        filtered_row: Dict[str, str],
        handlers: List[Any],
        row_idx: int,
        stats: StatsDict,
        max_row_errors: int,
    ) -> tuple[DataEntryTypeEnum | None, "ModuleHandler | None"]:
        """
        Shared Priority 1/2 of data_entry_type resolution.

        Priority 1: configured ``data_entry_type_id`` from job config
        (cast through int so string ids from JSON config work).
        Priority 2: the single handler's category column (e.g.
        ``equipment_category``) mapping directly to a DataEntryTypeEnum
        name.

        Returns (data_entry_type, handler); either may be None — callers
        decide whether that is an error (MODULE_UNIT_SPECIFIC) or the
        cue for factor-based inference (MODULE_PER_YEAR).
        """
        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        if configured_data_entry_type_id is not None:
            data_entry_type = DataEntryTypeEnum(int(configured_data_entry_type_id))
            return data_entry_type, handlers[0] if handlers else None

        handler = handlers[0] if len(handlers) == 1 else None
        if handler is None:
            return None, None

        data_entry_type = self._resolve_data_entry_type_from_category(
            filtered_row, handler, row_idx, stats, max_row_errors
        )
        return data_entry_type, handler
```

- [ ] **Step 4: Update the stale comment in `_process_row`**

In `base_csv_provider.py` around line 907 there is a comment block:

```python
                # Defense in depth: setup-time guards in the entity-specific
                # providers (_setup_handlers_and_factors for
                # MODULE_UNIT_SPECIFIC, _resolve_module_per_year_modules for
                # MODULE_PER_YEAR) raise before any row reaches this method,
```

Change those four lines to:

```python
                # Defense in depth: the setup-time guard in
                # _load_handlers_and_factors raises before any row
                # reaches this method,
```

(keep the rest of that comment block unchanged).

- [ ] **Step 5: Run the unit suite — must stay green (helpers are not wired yet)**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/ -q
```

Expected: PASS (same count as Task 1 baseline).

- [ ] **Step 6: Commit**

```bash
git add app/services/data_ingestion/base_csv_provider.py
git commit -m "refactor(csv-ingestion): add shared setup/resolve helpers to BaseCSVProvider"
```

---

### Task 3: Migrate ModulePerYearCSVProvider

**Files:**

- Modify: `backend/app/services/data_ingestion/csv_providers/module_per_year.py`
- Test: `backend/tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py`

- [ ] **Step 1: Write the failing regression tests**

Add to the imports at the top of `test_module_per_year_csv_provider.py`:

```python
from app.services.data_ingestion import base_csv_provider as base_csv_provider_module
```

Append these two tests at the end of the file:

```python
@pytest.mark.asyncio
async def test_setup_raises_when_year_missing(monkeypatch):
    """Regression: MODULE_PER_YEAR setup must fail loudly without ``year``.

    Factor lookups key on ``{type}:{year}:{kind}:{subkind}``; a missing
    year silently misses every factor. MODULE_UNIT_SPECIFIC already had
    this guard — converged into the shared loader."""
    provider = ModulePerYearCSVProvider(
        {"file_path": "tmp/test.csv"},  # year deliberately omitted
        data_session=MagicMock(),
    )
    provider.job = SimpleNamespace(module_type_id=ModuleTypeEnum.headcount.value)

    with pytest.raises(ValueError, match="year is required"):
        await provider._setup_handlers_and_factors()


@pytest.mark.asyncio
async def test_resolve_configured_type_accepts_string_id():
    """Regression: job config may carry data_entry_type_id as a string
    (JSON payload). MODULE_UNIT_SPECIFIC cast through int(); MODULE_PER_YEAR
    did not — converged in the shared resolver."""
    provider = ModulePerYearCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": str(DataEntryTypeEnum.member.value),
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=False,
        kind_field="kind",
        subkind_field=None,
        category_field=None,
    )
    setup_result = {"handlers": [handler], "factors_map": {}}
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={},
        factor=None,
        stats=stats,
        row_idx=1,
        max_row_errors=5,
        setup_result=setup_result,
    )

    assert data_entry_type == DataEntryTypeEnum.member
    assert resolved_handler == handler
    assert error_msg is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py::test_setup_raises_when_year_missing tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py::test_resolve_configured_type_accepts_string_id -v
```

Expected: both FAIL (`test_setup_raises_when_year_missing` raises nothing / DID NOT RAISE; `test_resolve_configured_type_accepts_string_id` errors with `ValueError: '3' is not a valid DataEntryTypeEnum` or similar).

- [ ] **Step 3: Update the existing tests for the new loader location**

Four existing tests call `_setup_handlers_and_factors` and will now hit the year guard, and their `load_factors_map` monkeypatch must point at the base module. Apply ALL of the following edits in `test_module_per_year_csv_provider.py`:

In `test_setup_handlers_and_factors_multiple_types`, `test_equipment_with_empty_factors_fails_fast_at_setup`, `test_purchase_with_empty_factors_fails_fast_at_setup`, and `test_non_factor_inferred_module_tolerates_empty_factors`:

1. Change the provider construction config from `{"file_path": "tmp/test.csv"}` to `{"file_path": "tmp/test.csv", "year": 2025}`.
2. Change the monkeypatch target

```python
    monkeypatch.setattr(
        csv_providers_module.module_per_year,
        "load_factors_map",
        ...
    )
```

to

```python
    monkeypatch.setattr(
        base_csv_provider_module,
        "load_factors_map",
        ...
    )
```

(keep each test's `AsyncMock(return_value=...)` argument exactly as it is).

Leave the `BaseModuleHandler` monkeypatches in this file unchanged — `module_per_year` keeps importing `BaseModuleHandler`, and patching `get_by_type` mutates the shared class object, so the base-class loader sees the patch too.

Leave `test_setup_handlers_and_factors_invalid_data_entry_type` unchanged: the validity check fires before the loader, so no year is needed.

- [ ] **Step 4: Rewrite `module_per_year.py`**

Replace the entire contents of `backend/app/services/data_ingestion/csv_providers/module_per_year.py` with:

```python
from typing import Any, Dict

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.schemas.data_entry import BaseModuleHandler, ModuleHandler
from app.seed.seed_helper import lookup_data_entry_type_by_kind
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
)

logger = get_logger(__name__)


# Module types whose CSV ingest INFERS the per-row ``data_entry_type_id``
# from a matched Factor (the row carries a kind/sub-kind, not a DET name,
# so the resolver looks up the factor table to disambiguate which DET
# the row belongs to).  An empty factors_map for these modules means
# every row's resolution will fail with "no matching factor found in
# factors map" — the operator gains nothing from grinding through
# 50 000 rows of the same error; refuse the ingest up front.
#
# Other modules (e.g. ``buildings``, ``professional_travel``,
# ``headcount``) carry the DET in a category column that maps directly
# to ``DataEntryTypeEnum`` names, so an empty factors_map is a
# legitimate state (they ingest rows with ``primary_factor_id=None``).
_FACTOR_INFERRED_MODULES: set[ModuleTypeEnum] = {
    ModuleTypeEnum.equipment_electric_consumption,
    ModuleTypeEnum.purchase,
}


class ModulePerYearCSVProvider(BaseCSVProvider):
    """
    CSV provider for MODULE_PER_YEAR entity type.

    Handles module-level data like travel or headcount per year.
    Determines data_entry_type from the factor (kind/subkind) found in the row.
    """

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """
        Setup handlers and factors for MODULE_PER_YEAR.

        Loads handlers/factors for all valid data_entry_types of the
        module (or just the configured one), then assembles the shared
        setup dict. unit_institutional_id is the only required column —
        per-row type resolution is flexible (config, category column, or
        factor inference).
        """
        if self.job is None or self.job.module_type_id is None:
            raise Exception(
                "module_type_id must be set for MODULE_PER_YEAR entity type"
            )

        module_type = ModuleTypeEnum(self.job.module_type_id)
        valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

        if not valid_entry_types:
            raise Exception(
                f"No data entry types defined for module type: {module_type}"
            )

        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        if configured_data_entry_type_id is not None:
            configured_data_entry_type = DataEntryTypeEnum(
                int(configured_data_entry_type_id)
            )
            if configured_data_entry_type not in valid_entry_types:
                raise Exception(
                    f"data_entry_type {configured_data_entry_type} "
                    f"not valid for module type {module_type}"
                )
            entry_types = [configured_data_entry_type]
        else:
            entry_types = list(valid_entry_types)

        handlers, factors_map = await self._load_handlers_and_factors(entry_types)

        # Fail fast for "common" uploads — modules that infer the per-row
        # data_entry_type_id by looking up the row's kind/sub-kind in the
        # factors map (equipment, purchase).  An empty factors_map
        # guarantees every row will fail with "no matching factor found";
        # surfacing that as one terminal error beats 50 000 row-level
        # errors that all point at the same missing-factors fix.  Other
        # modules (whose category column maps directly to DET names) are
        # legitimately allowed an empty map and are covered by the
        # narrower ``_guard_factors_required`` check in
        # ``_assemble_setup_result``.
        if module_type in _FACTOR_INFERRED_MODULES and not factors_map:
            year_str = (
                f"year={self.year}" if self.year is not None else "the configured year"
            )
            raise ValueError(
                f"No factors available for module={module_type.name} {year_str}. "
                "This module infers the per-row data_entry_type from a matched "
                "Factor, so an empty factors table guarantees every row will "
                "fail. Upload factors for this module/year before ingesting data."
            )

        # unit_institutional_id required for MODULE_PER_YEAR
        return self._assemble_setup_result(
            handlers=handlers,
            factors_map=factors_map,
            module_label=module_type.name,
            required_columns={"unit_institutional_id"},
        )

    async def _resolve_handler_and_validate(
        self,
        filtered_row: Dict[str, str],
        factor: Any | None,
        stats: StatsDict,
        row_idx: int,
        max_row_errors: int,
        setup_result: Dict[str, Any],
    ) -> tuple[DataEntryTypeEnum | None, "ModuleHandler | None", str | None]:
        """
        Resolve handler and validate for MODULE_PER_YEAR.

        Logic:
        - Priority 1/2 (configured data_entry_type_id, then the handler's
          category column) via the shared base resolver
        - Priority 3: infer the type from the factors map (kind/subkind)
        - Note: factor validation is handled by ModuleHandlerService
          when it queries the database in _process_row
        """
        handlers = setup_result["handlers"]

        data_entry_type, handler = self._resolve_type_from_config_or_category(
            filtered_row, handlers, row_idx, stats, max_row_errors
        )

        if data_entry_type is None:
            # Priority 3: infer from the factors map already loaded at
            # setup (NOT per-row DB queries)
            if self.job is None or self.job.module_type_id is None:
                error_msg = "module_type_id must be set for MODULE_PER_YEAR"
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

            module_type = ModuleTypeEnum(self.job.module_type_id)
            valid_entry_types = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])

            original_map = setup_result["factors_map"]
            factors_maps_by_type: Dict[DataEntryTypeEnum, Dict[str, Any]] = {}
            for entry_type in valid_entry_types:
                # Factor-map keys are prefixed "{type_value}:" — split the
                # merged map back per type for the lookup helper
                prefix = f"{entry_type.value}:"
                factors_maps_by_type[entry_type] = {
                    key: factor
                    for key, factor in original_map.items()
                    if key.startswith(prefix)
                }

            kind_value, subkind_value = self._extract_kind_subkind_values(
                filtered_row, handlers
            )

            data_entry_type = lookup_data_entry_type_by_kind(
                kind=kind_value,
                subkind=subkind_value,
                factors_maps_by_type=factors_maps_by_type,
            )

            if data_entry_type is None:
                error_msg = (
                    "Missing data_entry_type_id in job config, category field,"
                    " or factor and no matching factor found in factors map"
                    f" (kind={kind_value}, subkind={subkind_value})"
                )
                self._record_row_error(stats, row_idx, error_msg, max_row_errors)
                return None, None, error_msg

        if handler is None:
            handler = BaseModuleHandler.get_by_type(data_entry_type)

        if not handler:
            error_msg = "No handler available"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        return data_entry_type, handler, None
```

Deltas vs the old file, for the reviewer's benefit:

- `_extract_kind_subkind_values` deleted (now inherited from base).
- Setup delegates loading/dedup/guard/assembly to the base helpers; the `_FACTOR_INFERRED_MODULES` fail-fast stays here, between loading and assembly, preserving error precedence.
- `lookup_data_entry_type_by_kind` import moved from inline (inside the method) to the top of the file.
- `int()` cast added on the configured id in both setup and (via the shared resolver) row resolution.
- The unreachable duplicate `data_entry_type is None` error block (old lines 317–325) is gone — the Priority-3 branch already returns on failure.

- [ ] **Step 5: Run the module_per_year tests**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py -v
```

Expected: ALL PASS, including the two new regression tests.

- [ ] **Step 6: Run the full ingestion unit suite (cross-provider fallout check)**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/ -q
```

Expected: PASS. (`test_module_unit_specific_csv_provider.py` is untouched so far and must still pass — unit_specific still has its own implementations until Task 4.)

- [ ] **Step 7: Commit**

```bash
git add app/services/data_ingestion/csv_providers/module_per_year.py tests/unit/services/data_ingestion/test_module_per_year_csv_provider.py
git commit -m "refactor(csv-ingestion): migrate ModulePerYearCSVProvider to shared base helpers"
```

---

### Task 4: Migrate ModuleUnitSpecificCSVProvider

**Files:**

- Modify: `backend/app/services/data_ingestion/csv_providers/module_unit_specific.py`
- Test: `backend/tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py`

- [ ] **Step 1: Write the failing regression test for the converged factor behavior**

In `test_module_unit_specific_csv_provider.py`, REPLACE the entire test `test_resolve_handler_and_validate_missing_factor` (including its `monkeypatch` parameter and the `is_in_factors_map` monkeypatch inside it) with:

```python
@pytest.mark.asyncio
async def test_resolve_handler_and_validate_configured_type_missing_factor():
    """Converged with MODULE_PER_YEAR: a configured data_entry_type with an
    empty factors_map passes row resolution — factor lookup and validation
    happen later via ModuleHandlerService. The early is_in_factors_map
    rejection was a fork and is gone."""
    provider = ModuleUnitSpecificCSVProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        require_factor_to_match=True,
        require_subkind_for_factor=False,
        kind_field="kind",
        subkind_field="subkind",
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {},  # empty — must NOT reject the row anymore
        "required_columns": set(),
    }
    stats = _build_stats()

    (
        data_entry_type,
        resolved_handler,
        error_msg,
    ) = await provider._resolve_handler_and_validate(
        filtered_row={"kind": "k1"},
        factor=None,
        stats=stats,
        row_idx=2,
        max_row_errors=5,
        setup_result=setup_result,
    )

    assert data_entry_type == DataEntryTypeEnum.member
    assert resolved_handler == handler
    assert error_msg is None
    assert stats["rows_skipped"] == 0
```

- [ ] **Step 2: Run it to verify it fails against the current implementation**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py::test_resolve_handler_and_validate_configured_type_missing_factor -v
```

Expected: FAIL (current code returns the "No matching factor found for kind/subkind" error).

- [ ] **Step 3: Update the remaining tests in the file**

Apply ALL of the following edits in `test_module_unit_specific_csv_provider.py`:

1. Add to the imports at the top:

```python
from app.services.data_ingestion import base_csv_provider as base_csv_provider_module
```

2. In these five tests — `test_setup_handlers_and_factors_single_type`, `test_setup_returns_empty_factor_id_map_with_no_factors`, `test_setup_returns_multiple_factors_in_id_map`, `test_setup_skips_factors_without_id`, `test_all_data_entry_types_return_factor_id_to_factor` — retarget BOTH monkeypatches. Change:

```python
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "load_factors_map",
        AsyncMock(return_value=...),
    )
```

to:

```python
    monkeypatch.setattr(
        base_csv_provider_module.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        base_csv_provider_module,
        "load_factors_map",
        AsyncMock(return_value=...),
    )
```

(keep each test's `AsyncMock(return_value=...)` argument exactly as it is; `module_unit_specific` no longer imports either name, so the old targets would raise `AttributeError`).

3. In `test_resolve_handler_and_validate_factor_mismatch`: delete the `monkeypatch` parameter and the entire `monkeypatch.setattr(... "is_in_factors_map" ...)` call (`is_in_factors_map` no longer exists in the module). Keep all assertions unchanged.

4. Delete the empty stub test `test_setup_no_handler_for_type` (it has a docstring-free empty body — dead code).

5. If the file still references `csv_providers_module` after these edits, keep its import; if nothing references it anymore, remove the import. (After the edits above, `test_module_unit_specific_csv_provider.py` should have no remaining `csv_providers_module` usages — remove the import.)

- [ ] **Step 4: Rewrite `module_unit_specific.py`**

Replace the entire contents of `backend/app/services/data_ingestion/csv_providers/module_unit_specific.py` with:

```python
from typing import Any, Dict

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType
from app.schemas.data_entry import ModuleHandler
from app.services.data_ingestion.base_csv_provider import (
    BaseCSVProvider,
    StatsDict,
    _get_required_columns_from_handler,
)

logger = get_logger(__name__)


class ModuleUnitSpecificCSVProvider(BaseCSVProvider):
    """
    CSV provider for MODULE_UNIT_SPECIFIC entity type.

    Handles unit-specific data like equipment per carbon report module.
    Requires a single data_entry_type and associated carbon_report_module_id.
    """

    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_UNIT_SPECIFIC

    async def _setup_handlers_and_factors(self) -> Dict[str, Any]:
        """
        Setup handlers and factors for MODULE_UNIT_SPECIFIC.

        Single handler for the configured data_entry_type, with strict
        required-column validation derived from the handler's DTO.
        """
        configured_data_entry_type_id = self.config.get("data_entry_type_id")

        if configured_data_entry_type_id is None:
            raise Exception(
                "data_entry_type must be specified for MODULE_UNIT_SPECIFIC"
            )

        configured_data_entry_type = DataEntryTypeEnum(
            int(configured_data_entry_type_id)
        )

        handlers, factors_map = await self._load_handlers_and_factors(
            [configured_data_entry_type]
        )

        return self._assemble_setup_result(
            handlers=handlers,
            factors_map=factors_map,
            module_label=configured_data_entry_type.name,
            required_columns=_get_required_columns_from_handler(handlers[0]),
        )

    async def _resolve_handler_and_validate(
        self,
        filtered_row: Dict[str, str],
        factor: Any | None,
        stats: StatsDict,
        row_idx: int,
        max_row_errors: int,
        setup_result: Dict[str, Any],
    ) -> tuple[DataEntryTypeEnum | None, "ModuleHandler | None", str | None]:
        """
        Resolve handler and validate for MODULE_UNIT_SPECIFIC.

        Logic:
        - Priority 1/2 (configured data_entry_type_id, then the handler's
          category column) via the shared base resolver — no factor-based
          inference for this entity type
        - Validate required columns are present (strict)
        - Note: factor validation is handled by ModuleHandlerService
          when it queries the database in _process_row
        """
        handlers = setup_result["handlers"]
        required_columns = setup_result["required_columns"]

        data_entry_type, handler = self._resolve_type_from_config_or_category(
            filtered_row, handlers, row_idx, stats, max_row_errors
        )

        if data_entry_type is None:
            error_msg = (
                "Missing data_entry_type_id in job config or category field in CSV"
            )
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        if handler is None:
            error_msg = "No handler available"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        if required_columns and not required_columns.issubset(filtered_row.keys()):
            missing_fields = required_columns - set(filtered_row.keys())
            error_msg = f"Missing required fields {missing_fields}"
            self._record_row_error(stats, row_idx, error_msg, max_row_errors)
            return None, None, error_msg

        return data_entry_type, handler, None
```

Deltas vs the old file, for the reviewer's benefit:

- `_extract_kind_subkind_values` deleted (inherited from base; the single-handler case is n=1).
- Setup delegates year guard, loading, require-factor guard, and assembly to the base helpers.
- The early `is_in_factors_map` / `require_factor_to_match` row rejection is REMOVED (agreed convergence with MODULE_PER_YEAR — `ModuleHandlerService` validates factors during row processing).
- Imports of `BaseModuleHandler`, `load_factors_map`, `is_in_factors_map`, `_get_expected_columns_from_handlers`, `_guard_factors_required`, and `List` dropped — all now live behind the base helpers.

- [ ] **Step 5: Run the module_unit_specific tests**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py -v
```

Expected: ALL PASS, including the rewritten `test_resolve_handler_and_validate_configured_type_missing_factor`.

- [ ] **Step 6: Run the full ingestion unit suite**

```bash
cd backend && uv run pytest tests/unit/services/data_ingestion/ -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/services/data_ingestion/csv_providers/module_unit_specific.py tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py
git commit -m "refactor(csv-ingestion): migrate ModuleUnitSpecificCSVProvider to shared base helpers"
```

---

### Task 5: Full verification

- [ ] **Step 1: Full backend unit suite**

```bash
cd backend && uv run pytest tests/unit -q
```

Expected: PASS (other providers — factors, reference_data, reduction_objectives — subclass the same base; this catches any fallout from making `_extract_kind_subkind_values` concrete).

- [ ] **Step 2: Ingestion integration suites (needs the local test database)**

```bash
cd backend && uv run pytest tests/integration/services/data_ingestion tests/integration/data_ingestion -q
```

Expected: PASS. These exercise the real end-to-end CSV paths (`test_csv_ingest_matrix_pg.py`, `test_csv_upload_e2e.py`, `test_reupload_semantics_pg.py`). If the database is not available, report that these were skipped and why — do not claim them green.

- [ ] **Step 3: Lint and type-check**

```bash
cd backend && make lint && make type-check
```

Expected: both clean. Common trip-up: unused imports left behind in the rewritten files (ruff will flag them) — fix and amend the relevant commit.

- [ ] **Step 4: Commit any verification fixups**

```bash
git add -A && git commit -m "refactor(csv-ingestion): verification fixups"
```

(Skip this commit if there is nothing to fix.)

- [ ] **Step 5: Stop and report**

Do NOT open a PR. Summarize: line-count delta per file, test results (exact pass counts), and any deviation from this plan. The maintainer reviews before anything ships.

---

## Out of scope (deliberately)

- The `entity_type == MODULE_PER_YEAR` branches inside `BaseCSVProvider` (carbon-report-module resolution, delete-and-replace semantics, `DataEntrySourceEnum` mapping) — real lifecycle differences, not drift.
- `_resolve_carbon_report_modules`'s own year guard — redundant with the new loader guard but harmless defense in depth; removing it would widen the diff for no behavior change.
- The other three providers (`factors.py`, `reference_data.py`, `reduction_objectives.py`) — they may benefit from the same helpers later, but converging two providers correctly beats converging five sloppily.
