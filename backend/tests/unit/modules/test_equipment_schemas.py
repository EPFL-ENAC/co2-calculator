"""Equipment validation permutation matrix (data + factor create DTOs).

One falsifiable case per field-level rule in the ``equipments_data.csv`` and
``equipments_factors.csv`` contracts (data-description.md → Equipment):

data (EquipmentHandlerCreate)
    equipment_id                 ✅ non-empty (letters and numbers)
    name                         ✅ non-empty
    equipment_class              ✅ non-empty (membership checked at runtime)
    sub_class                    ❌ optional
    active_usage_hours_per_week  ❌ optional, 0 ≤ int ≤ 168
    standby_usage_hours_per_week ❌ optional, 0 ≤ int ≤ 168, active+standby ≤ 168
    note                         ❌ optional

factor (EquipmentFactorCreate)
    equipment_category           ✅ case-sensitive enum {scientific, it, other}
    equipment_class              ✅
    sub_class                    ❌ optional
    active_usage_hours_per_week  ✅ 0 ≤ int ≤ 168
    standby_usage_hours_per_week ✅ 0 ≤ int ≤ 168
    active_power_w               ✅ ≥ 0
    standby_power_w              ✅ ≥ 0
    ef_kg_co2eq_per_kwh          ✅ ≥ 0
"""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.data_entry import DataEntryTypeEnum
from app.modules.emissions import EmissionType
from app.modules.equipment import (
    EquipmentFactorCreate,
    EquipmentHandlerCreate,
    EquipmentHandlerResponse,
)
from app.schemas.data_entry import BaseModuleHandler

_OMIT = object()

_DATA_META = {
    "data_entry_type_id": DataEntryTypeEnum.scientific.value,
    "carbon_report_module_id": 1,
}
_FACTOR_META = {
    "data_entry_type_id": DataEntryTypeEnum.scientific.value,
    "emission_type_id": int(EmissionType.equipment),
}


def _data(**overrides) -> dict:
    payload = {
        **_DATA_META,
        "equipment_id": "INV-001",
        "name": "GoPro",
        "equipment_class": "Monitor",
        "active_usage_hours_per_week": 20,
        "standby_usage_hours_per_week": 10,
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not _OMIT}


def _factor(**overrides) -> dict:
    # equipment_category is NOT on the factor DTO — it is the routing column,
    # validated in the CSV provider (case-sensitive {scientific,it,other}).
    payload = {
        **_FACTOR_META,
        "equipment_class": "Evaporator",
        "active_usage_hours_per_week": 20,
        "standby_usage_hours_per_week": 10,
        "active_power_w": 23.0,
        "standby_power_w": 5.0,
        "ef_kg_co2eq_per_kwh": 0.125,
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not _OMIT}


# ---------------------------------------------------------------------------
# Data entry — valid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_data(), id="baseline"),
        pytest.param(_data(sub_class="ultra centrifuges"), id="sub_class-present"),
        pytest.param(
            _data(
                active_usage_hours_per_week=_OMIT, standby_usage_hours_per_week=_OMIT
            ),
            id="hours-omitted",
        ),
        pytest.param(
            _data(active_usage_hours_per_week=0, standby_usage_hours_per_week=0),
            id="hours-zero",
        ),
        pytest.param(
            _data(active_usage_hours_per_week=100, standby_usage_hours_per_week=68),
            id="hours-sum-168",
        ),
        pytest.param(
            _data(active_usage_hours_per_week=168, standby_usage_hours_per_week=0),
            id="active-max",
        ),
        pytest.param(_data(note="bench unit"), id="note-present"),
        pytest.param(_data(name="  GoPro  "), id="name-stripped"),
    ],
)
def test_equipment_data_valid(payload: dict) -> None:
    item = EquipmentHandlerCreate.model_validate(payload)
    assert item.equipment_id


# ---------------------------------------------------------------------------
# Data entry — invalid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_data(equipment_id=_OMIT), id="equipment_id-missing"),
        pytest.param(_data(equipment_id=""), id="equipment_id-empty"),
        pytest.param(_data(equipment_id="   "), id="equipment_id-whitespace"),
        pytest.param(_data(name=_OMIT), id="name-missing"),
        pytest.param(_data(name=""), id="name-empty"),
        pytest.param(_data(name="   "), id="name-whitespace"),
        pytest.param(_data(equipment_class=_OMIT), id="equipment_class-missing"),
        pytest.param(_data(equipment_class=""), id="equipment_class-empty"),
        pytest.param(_data(active_usage_hours_per_week=200), id="active-over-168"),
        pytest.param(_data(active_usage_hours_per_week=-1), id="active-negative"),
        pytest.param(_data(standby_usage_hours_per_week=200), id="standby-over-168"),
        pytest.param(
            _data(active_usage_hours_per_week=100, standby_usage_hours_per_week=100),
            id="sum-over-168",
        ),
    ],
)
def test_equipment_data_invalid(payload: dict) -> None:
    with pytest.raises(ValidationError):
        EquipmentHandlerCreate.model_validate(payload)


# ---------------------------------------------------------------------------
# Factor — valid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_factor(), id="baseline"),
        pytest.param(_factor(sub_class="ultra centrifuges"), id="sub_class-present"),
        pytest.param(
            _factor(active_power_w=0, standby_power_w=0, ef_kg_co2eq_per_kwh=0),
            id="zeros-allowed",
        ),
        pytest.param(
            _factor(active_usage_hours_per_week=0, standby_usage_hours_per_week=0),
            id="hours-zero",
        ),
    ],
)
def test_equipment_factor_valid(payload: dict) -> None:
    item = EquipmentFactorCreate.model_validate(payload)
    assert item.equipment_class


# ---------------------------------------------------------------------------
# Factor — invalid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_factor(equipment_class=_OMIT), id="equipment_class-missing"),
        pytest.param(_factor(active_usage_hours_per_week=_OMIT), id="active-missing"),
        pytest.param(_factor(standby_usage_hours_per_week=_OMIT), id="standby-missing"),
        pytest.param(_factor(active_power_w=_OMIT), id="active_power-missing"),
        pytest.param(_factor(ef_kg_co2eq_per_kwh=_OMIT), id="ef-missing"),
        pytest.param(_factor(active_power_w=-1.0), id="active_power-negative"),
        pytest.param(_factor(ef_kg_co2eq_per_kwh=-0.1), id="ef-negative"),
        pytest.param(_factor(active_usage_hours_per_week=200), id="active-over-168"),
    ],
)
def test_equipment_factor_invalid(payload: dict) -> None:
    with pytest.raises(ValidationError):
        EquipmentFactorCreate.model_validate(payload)


# ── live hour defaults (plan 1661-sql-factor-resolution step 6) ─────────


def _compute_kg(entry_data: dict, factor_values: dict) -> float | None:
    """Run the equipment formula the way prepare_create does: ctx wins,
    factor values are the live default for unset usage hours.
    """
    handler = BaseModuleHandler.get_by_type(DataEntryTypeEnum.it)
    entry = SimpleNamespace(
        data_entry_type_id=DataEntryTypeEnum.it.value, data=entry_data
    )
    ctx = {**entry_data, "primary_factor_id": 1}
    comps = handler.resolve_computations(entry, EmissionType.equipment__it, ctx)
    assert len(comps) == 1
    formula = comps[0].formula_func
    assert formula is not None
    return formula(ctx, factor_values)


def test_equipment_formula_user_hours_win_over_factor_defaults() -> None:
    kg = _compute_kg(
        {"active_usage_hours_per_week": 10, "standby_usage_hours_per_week": 0},
        {
            "active_power_w": 100.0,
            "standby_power_w": 10.0,
            "ef_kg_co2eq_per_kwh": 1.0,
            "active_usage_hours_per_week": 40,
            "standby_usage_hours_per_week": 128,
        },
    )
    settings_weeks = get_settings().WEEKS_PER_YEAR
    assert kg == pytest.approx((10 * 100.0) * settings_weeks / 1000)


def test_equipment_formula_falls_back_to_factor_hours_when_unset() -> None:
    """Unset usage hours track the factor's current suggestion — nothing is
    seeded into entry.data at ingest any more.
    """
    kg = _compute_kg(
        {},  # no hours on the entry
        {
            "active_power_w": 100.0,
            "standby_power_w": 10.0,
            "ef_kg_co2eq_per_kwh": 1.0,
            "active_usage_hours_per_week": 40,
            "standby_usage_hours_per_week": 128,
        },
    )
    settings_weeks = get_settings().WEEKS_PER_YEAR
    expected_weekly_wh = 40 * 100.0 + 128 * 10.0
    assert kg == pytest.approx(expected_weekly_wh * settings_weeks / 1000)


def test_equipment_formula_none_when_no_hours_anywhere() -> None:
    kg = _compute_kg(
        {},
        {"active_power_w": 100.0, "standby_power_w": 10.0, "ef_kg_co2eq_per_kwh": 1.0},
    )
    assert kg is None


# ── response DTO accepts fractional power (regression, stage 500 on entry 385685) ──


def test_equipment_response_accepts_fractional_power_w() -> None:
    """EquipmentFactorCreate has allowed float active/standby_power_w since the
    equipment_factors.csv contract moved off int; EquipmentHandlerResponse must
    accept the same values it enriches data entries with, or to_response() 500s.
    """
    item = EquipmentHandlerResponse.model_validate(
        {
            "id": 385685,
            **_DATA_META,
            "name": "GoPro",
            "equipment_class": "Monitor",
            "active_power_w": 2.0,
            "standby_power_w": 2.368421053,
        }
    )
    assert item.standby_power_w == pytest.approx(2.368421053)
