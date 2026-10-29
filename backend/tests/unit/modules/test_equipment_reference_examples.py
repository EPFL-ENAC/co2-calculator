"""Equipment reference examples (#2771):
(active_W × active_h + standby_W × standby_h) / 1000 × weeks/year × ef.

Rows: back-office doc, "test calculation equipment". Factors:
equipment_factors.csv (active_power_w, standby_power_w, ef_kg_co2eq_per_kwh).
"""

import pytest

from app.core.config import get_settings
from app.models.data_entry import DataEntryTypeEnum
from app.modules.equipment import EquipmentModuleHandler
from tests.unit.modules.reference_examples import TOLERANCE_KG, compute_kg_co2eq

# The doc's examples count 47 weeks a year; production defaults to 52.
_DOC_WEEKS_PER_YEAR = 47

_SCIENTIFIC = DataEntryTypeEnum.scientific


@pytest.mark.parametrize(
    ("data_entry_type", "hours", "power_w", "expected_kg"),
    [
        pytest.param(_SCIENTIFIC, (24, 144), (100.0, 0.0), 10.94, id="EQ001"),
        pytest.param(_SCIENTIFIC, (24, 144), (20.0, 10.0), 8.75, id="EQ002"),
        pytest.param(_SCIENTIFIC, (24, 144), (64000.0, 100.0), 7068.27, id="EQ003"),
        pytest.param(_SCIENTIFIC, (24, 144), (2300.0, 30.0), 271.35, id="EQ004"),
        pytest.param(_SCIENTIFIC, (24, 144), (3500.0, 30.0), 402.65, id="EQ005"),
        pytest.param(
            DataEntryTypeEnum.it, (70, 98), (500.0, 100.0), 204.24, id="EQ007"
        ),
    ],
)
def test_equipment_reference_example(
    monkeypatch: pytest.MonkeyPatch,
    data_entry_type: DataEntryTypeEnum,
    hours: tuple[float, float],
    power_w: tuple[float, float],
    expected_kg: float,
) -> None:
    monkeypatch.setattr(get_settings(), "WEEKS_PER_YEAR", _DOC_WEEKS_PER_YEAR)
    ctx = {
        "active_usage_hours_per_week": hours[0],
        "standby_usage_hours_per_week": hours[1],
    }
    values = {
        "active_power_w": power_w[0],
        "standby_power_w": power_w[1],
        "ef_kg_co2eq_per_kwh": 0.097,
    }
    kg = compute_kg_co2eq(EquipmentModuleHandler(), data_entry_type, ctx, values)
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="#2771: doc uses 47 weeks/year, WEEKS_PER_YEAR defaults to 52",
)
def test_production_weeks_per_year_matches_doc() -> None:
    assert get_settings().WEEKS_PER_YEAR == _DOC_WEEKS_PER_YEAR
