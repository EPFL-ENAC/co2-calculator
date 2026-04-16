"""Tests for year_config_service — pure-logic helpers with no DB dependency."""

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import MODULE_TYPE_TO_DATA_ENTRY_TYPES, ModuleTypeEnum
from app.services.year_config_service import (
    check_threshold_exceeded,
    generate_default_year_config,
    get_module_config,
    get_submodule_config,
)

# ── generate_default_year_config ──────────────────────────────────────────────


def test_generate_default_year_config_has_modules():
    cfg = generate_default_year_config()
    assert "modules" in cfg
    # Every ModuleTypeEnum member should have an entry
    for module_type in ModuleTypeEnum:
        assert str(module_type.value) in cfg["modules"]


def test_generate_default_year_config_module_structure():
    cfg = generate_default_year_config()
    for module_type in ModuleTypeEnum:
        mod = cfg["modules"][str(module_type.value)]
        assert mod["enabled"] is True
        assert mod["uncertainty_tag"] == "medium"
        assert isinstance(mod["submodules"], dict)

        expected_subs = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(module_type, [])
        for det in expected_subs:
            sub = mod["submodules"][str(det.value)]
            assert sub == {"enabled": True, "threshold": None}


def test_generate_default_year_config_reduction_objectives():
    cfg = generate_default_year_config()
    ro = cfg["reduction_objectives"]
    assert ro["institutional_footprint"] == []
    assert ro["population_projections"] == []
    assert ro["unit_scenarios"] == []
    assert ro["goals"] == []
    assert ro["files"] == {
        "institutional_footprint": None,
        "population_projections": None,
        "unit_scenarios": None,
    }


# ── get_module_config ─────────────────────────────────────────────────────────


def test_get_module_config_found():
    cfg = generate_default_year_config()
    first_module = next(iter(ModuleTypeEnum))
    result = get_module_config(cfg, first_module)
    assert result is not None
    assert result["enabled"] is True


def test_get_module_config_missing():
    result = get_module_config({"modules": {}}, next(iter(ModuleTypeEnum)))
    assert result is None


def test_get_module_config_empty():
    result = get_module_config({}, next(iter(ModuleTypeEnum)))
    assert result is None


# ── get_submodule_config ──────────────────────────────────────────────────────


def test_get_submodule_config_found():
    cfg = generate_default_year_config()
    # Pick a module that has submodules
    for mt in ModuleTypeEnum:
        dets = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(mt, [])
        if dets:
            mod = get_module_config(cfg, mt)
            sub = get_submodule_config(mod, dets[0])
            assert sub is not None
            assert sub["enabled"] is True
            return
    pytest.skip("No module with submodules found")


def test_get_submodule_config_none_module():
    result = get_submodule_config(None, next(iter(DataEntryTypeEnum)))
    assert result is None


def test_get_submodule_config_empty_module():
    result = get_submodule_config({}, next(iter(DataEntryTypeEnum)))
    assert result is None


# ── check_threshold_exceeded ──────────────────────────────────────────────────


def _make_config_with_threshold(
    module_type: ModuleTypeEnum,
    data_entry_type: DataEntryTypeEnum,
    threshold: float | None,
) -> dict:
    cfg = generate_default_year_config()
    mod = cfg["modules"][str(module_type.value)]
    mod["submodules"][str(data_entry_type.value)]["threshold"] = threshold
    return cfg


def _first_module_and_sub():
    for mt in ModuleTypeEnum:
        dets = MODULE_TYPE_TO_DATA_ENTRY_TYPES.get(mt, [])
        if dets:
            return mt, dets[0]
    pytest.skip("No module with submodules found")


def test_check_threshold_exceeded_true():
    mt, det = _first_module_and_sub()
    cfg = _make_config_with_threshold(mt, det, 100.0)
    assert check_threshold_exceeded(cfg, mt, det, 200.0) is True


def test_check_threshold_exceeded_false():
    mt, det = _first_module_and_sub()
    cfg = _make_config_with_threshold(mt, det, 100.0)
    assert check_threshold_exceeded(cfg, mt, det, 50.0) is False


def test_check_threshold_none():
    mt, det = _first_module_and_sub()
    cfg = _make_config_with_threshold(mt, det, None)
    assert check_threshold_exceeded(cfg, mt, det, 999.0) is False


def test_check_threshold_no_submodule():
    mt = next(iter(ModuleTypeEnum))
    det = next(iter(DataEntryTypeEnum))
    # config with no submodules at all
    assert check_threshold_exceeded({"modules": {}}, mt, det, 10.0) is False
