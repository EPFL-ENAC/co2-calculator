---
status: in-progress
issue: 898
last_updated: 2026-05-06
title: "Fix ModuleUnitSpecificCSVProvider KeyError + Add CSV Fixture Tests"
summary: "Resolve KeyError on factor_id_to_factor in ModuleUnitSpecificCSVProvider; add fixture-based tests."
---

# Fix ModuleUnitSpecificCSVProvider KeyError + Add CSV Fixture Tests

## Bug Analysis

**Error**: `KeyError: 'factor_id_to_factor'` at `base_csv_provider.py:723`

**Root Cause**: `ModuleUnitSpecificCSVProvider._setup_handlers_and_factors()` returns a dict with keys `handlers`, `factors_map`, `expected_columns`, `required_columns` — but NOT `factor_id_to_factor`.

Meanwhile, `BaseCSVProvider._setup_and_validate()` at line 723 unconditionally expects `entity_setup["factor_id_to_factor"]`.

`ModulePerYearCSVProvider` does this correctly (lines 111-130 of `module_per_year.py`) — it builds and returns the `factor_id_to_factor` mapping.

**Fix in `module_unit_specific.py:59-76`**: Add `factor_id_to_factor` dict comprehension before the return, matching the pattern from `module_per_year.py:111-117`.

## Fix: backend/app/services/data_ingestion/csv_providers/module_unit_specific.py

**Lines 59-76** (replace):

```python
        # Get expected and required columns
        expected_columns = _get_expected_columns_from_handlers(handlers)
        required_columns = _get_required_columns_from_handler(handler)

        # Create factor_id_to_factor mapping for O(1) lookup during row processing
        # This avoids O(n) loop through factors_map for each row
        factor_id_to_factor: Dict[int, Any] = {}
        for factor in factors_map.values():
            factor_id = getattr(factor, "id", None)
            if factor_id is not None:
                factor_id_to_factor[factor_id] = factor

        logger.info(
            f"Setup complete for MODULE_UNIT_SPECIFIC: "
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
```

## Tests: backend/tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py

Add after line 217 (end of file):

### New fixtures section

```python
# ======================================================================
# CSV Fixtures for all data_entry_types
# ======================================================================

# Mapping of data_entry_type -> expected CSV headers
# Based on actual ModuleHandler create_dto.model_fields
CSV_FIXTURES = {
    DataEntryTypeEnum.member: {
        "headers": ["unit_institutional_id", "kind", "amount", "unit_of_measure"],
        "rows": [
            ["UNIT001", "Faculty", "25", "person"],
            ["UNIT002", "Staff", "40", "person"],
        ],
        "expected_count": 2,
    },
    DataEntryTypeEnum.student: {
        "headers": ["unit_institutional_id", "kind", "amount"],
        "rows": [
            ["UNIT001", "PhD", "10"],
            ["UNIT001", "Master", "50"],
            ["UNIT002", "Bachelor", "100"],
        ],
        "expected_count": 3,
    },
    DataEntryTypeEnum.scientific: {
        "headers": [
            "unit_institutional_id",
            "category",
            "make_and_model",
            "energy_type",
            "active_usage_hours_per_week",
            "standby_usage_hours_per_week",
            "number",
            "lifetime",
        ],
        "rows": [
            [
                "LAB001",
                "Centrifuge",
                "Model X",
                "electricity",
                "40",
                "20",
                "3",
                "10",
            ],
            ["LAB002", "Spectrometer", "Model Y", "electricity", "25", "10", "1", "8"],
        ],
        "expected_count": 2,
    },
    DataEntryTypeEnum.it: {
        "headers": [
            "unit_institutional_id",
            "category",
            "make_and_model",
            "energy_type",
            "active_usage_hours_per_week",
            "standby_usage_hours_per_week",
            "number",
            "lifetime",
        ],
        "rows": [
            [
                "OFF001",
                "Desktop",
                "Dell OptiPlex",
                "electricity",
                "40",
                "24",
                "15",
                "5",
            ],
            ["OFF002", "Laptop", "ThinkPad", "electricity", "35", "24", "50", "3"],
        ],
        "expected_count": 2,
    },
    DataEntryTypeEnum.other: {
        "headers": [
            "unit_institutional_id",
            "category",
            "make_and_model",
            "energy_type",
            "active_usage_hours_per_week",
            "standby_usage_hours_per_week",
            "number",
            "lifetime",
        ],
        "rows": [
            [
                "FAC001",
                "HVAC Unit",
                "Carrier AC",
                "electricity",
                "72",
                "72",
                "4",
                "15",
            ],
        ],
        "expected_count": 1,
    },
    DataEntryTypeEnum.plane: {
        "headers": [
            "unit_institutional_id",
            "kind",
            "subkind",
            "origin",
            "destination",
            "duration",
            "number",
            "class",
            "cdo_factor",
        ],
        "rows": [
            [
                "DEPT001",
                "Commercial",
                "Economy",
                "Zurich",
                "New York",
                "8",
                "2",
                "Economy",
                "0",
            ],
            ["DEPT001", "Commercial", "Business", "Geneva", "Tokyo", "12", "1", "Business", "0"],
        ],
        "expected_count": 2,
    },
    DataEntryTypeEnum.train: {
        "headers": [
            "unit_institutional_id",
            "kind",
            "subkind",
            "origin",
            "destination",
            "duration",
            "number",
            "cdo_factor",
        ],
        "rows": [
            ["DEPT001", "Long Distance", "1st Class", "Zurich", "Paris", "5", "2", "0"],
            ["DEPT002", "Regional", "2nd Class", "Lausanne", "Geneva", "1.5", "10", "0"],
        ],
        "expected_count": 2,
    },
}
```

### New test functions

```python
@pytest.mark.asyncio
async def test_setup_returns_factor_id_to_factor(member_type):
    """Verify _setup_handlers_and_factors returns factor_id_to_factor key."""
    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": member_type.value},
        data_session=MagicMock(),
    )

    mock_factor = MagicMock(id=42)
    handler = MagicMock()
    handler.create_dto.model_fields = {}

    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific,
        "load_factors_map",
        AsyncMock(return_value={"k": mock_factor}),
    )

    setup = await provider._setup_handlers_and_factors()

    assert "factor_id_to_factor" in setup
    assert setup["factor_id_to_factor"] == {42: mock_factor}


@pytest.mark.asyncio
async def test_resolve_handler_and_validate_with_category(monkeypatch):
    """Test resolving data_entry_type from category_field when not in config."""
    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv"},  # No data_entry_type_id in config
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(
        kind_field="kind",
        subkind_field=None,
        category_field="equipment_category",
        require_factor_to_match=False,
        require_subkind_for_factor=False,
    )
    setup_result = {
        "handlers": [handler],
        "factors_map": {"10:test": MagicMock()},
        "required_columns": {"kind"},
    }
    stats = _build_stats()

    (data_entry_type, resolved_handler, error_msg) = (
        await provider._resolve_handler_and_validate(
            filtered_row={"kind": "test", "equipment_category": "scientific"},
            factor=None,
            stats=stats,
            row_idx=1,
            max_row_errors=5,
            setup_result=setup_result,
        )
    )

    assert data_entry_type == DataEntryTypeEnum.scientific
    assert error_msg is None


def test_extract_kind_subkind_values_no_handler():
    """Test _extract_kind_subkind_values with empty handlers list."""
    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": DataEntryTypeEnum.member.value},
        data_session=MagicMock(),
    )

    kind, subkind = provider._extract_kind_subkind_values({"any": "row"}, [])

    assert kind == ""
    assert subkind is None


def test_extract_kind_subkind_values_missing_field():
    """Test _extract_kind_subkind_values when field doesn't exist in row."""
    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": DataEntryTypeEnum.member.value},
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(kind_field="kind", subkind_field="sub")
    filtered_row = {"other": "value"}

    kind, subkind = provider._extract_kind_subkind_values(filtered_row, [handler])

    assert kind == ""
    assert subkind is None


@pytest.mark.asyncio
async def test_resolve_from_category_missing_field(monkeypatch):
    """Test that missing category_field returns None data_entry_type."""
    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv"},
        data_session=MagicMock(),
    )

    handler = SimpleNamespace(category_field="nonexistent_field")
    setup_result = {
        "handlers": [handler],
        "factors_map": {},
        "required_columns": set(),
    }
    stats = _build_stats()

    (data_entry_type, resolved_handler, error_msg) = (
        await provider._resolve_handler_and_validate(
            filtered_row={},
            factor=None,
            stats=stats,
            row_idx=1,
            max_row_errors=5,
            setup_result=setup_result,
        )
    )

    assert data_entry_type is None
    assert "Missing data_entry_type_id" in error_msg


@pytest.mark.asyncio
async def test_setup_no_handler_for_type(monkeypatch):
    """Test error when no handler exists for data_entry_type."""
    monkeypatch.setattr(
        csv_providers_module.module_unit_specific.BaseModuleHandler,
        "get_by_type",
        side_effect=ValueError("No module handler found"),
    )

    provider = ModuleUnitSpecificCSVProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": 999},
        data_session=MagicMock(),
    )

    with pytest.raises(ValueError, match="No module handler found"):
        await provider._setup_handlers_and_factors()


# ======================================================================
# Parameterized tests fixture
# ======================================================================

@pytest.fixture(params=list(CSV_FIXTURES.keys()))
def csv_fixture_type(request):
    """Parameterized fixture for all CSV data_entry_types."""
    return request.param
```

## Verification

Run:

```bash
make test
```

Specific file:

```bash
cd backend && PYTEST= pytest tests/unit/services/data_ingestion/test_module_unit_specific_csv_provider.py -v
```

## Summary of changes

| File                                        | Lines     | Change                                                                     |
| ------------------------------------------- | --------- | -------------------------------------------------------------------------- |
| `module_unit_specific.py`                   | 59-76     | Added `factor_id_to_factor` dict comprehension + return key (10 new lines) |
| `test_module_unit_specific_csv_provider.py` | After 217 | Added CSV fixtures + 7 new tests (~150 lines)                              |
