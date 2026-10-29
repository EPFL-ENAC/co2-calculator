"""Buildings reference examples (#2771).

Rows: back-office doc, "test calculation building_energycombustion" and
"test calculation building_rooms". Factors: building_energycombustions_factors.csv
and building_rooms_factors.csv.
"""

from dataclasses import dataclass

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.buildings import (
    BuildingRoomModuleHandler,
    EnergyCombustionModuleHandler,
)
from tests.unit.modules.reference_examples import TOLERANCE_KG, compute_kg_co2eq


@dataclass
class _RoomFactor:
    """The factor fields the room leaf resolver reads (energy_type)."""

    classification: dict
    id: int | None = 1


def _room_values(
    lighting: float,
    ventilation: float,
    heating: float,
    cooling: float,
    conversion_factor: float,
) -> dict:
    return {
        "lighting_kwh_per_square_meter": lighting,
        "ventilation_kwh_per_square_meter": ventilation,
        "heating_kwh_per_square_meter": heating,
        "cooling_kwh_per_square_meter": cooling,
        "ef_kg_co2eq_per_kwh": 0.097,
        "conversion_factor": conversion_factor,
    }


_AAB_OFFICE = _room_values(5.189, 5.866, 2.293, 0.748, 1.0)
_AAB_MISC = _room_values(5.339, 17.798, 3.257, 1.033, 1.0)
_CSV_LIBRARIES = _room_values(3.952, 5.104, 35.594, 0.069, 2.8296988041649485)
_SOS1_ARCHIVES = _room_values(0.857, 1.404, 1.154, 0.094, 2.8297)
_CCT_OFFICE = _room_values(381.421, 431.142, 168.571, 54.965, 1.0)


@pytest.mark.parametrize(
    ("name", "quantity", "ef", "expected_kg"),
    [
        pytest.param("natural_gas", 100, 0.24, 24, id="natural_gas"),
        pytest.param("heating_oil", 50, 0.3243, 16.22, id="heating_oil"),
        pytest.param("biomethane", 200, 0.0444, 8.88, id="biomethane"),
        pytest.param("propane", 75, 0.2717, 20.38, id="propane"),
        pytest.param("pellets", 500, 0.1108, 55.40, id="pellets"),
        pytest.param("forest_chips", 1000, 0.0503, 50.30, id="forest_chips"),
        pytest.param("wood_logs", 250, 0.1138, 28.45, id="wood_logs"),
    ],
)
def test_energy_combustion_reference_example(
    name: str, quantity: float, ef: float, expected_kg: float
) -> None:
    kg = compute_kg_co2eq(
        EnergyCombustionModuleHandler(),
        DataEntryTypeEnum.energy_combustion,
        {"name": name, "quantity": quantity},
        {"ef_kg_co2eq_per_unit": ef},
    )
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)


@pytest.mark.parametrize(
    (
        "room_name",
        "room_type",
        "ratio",
        "surface",
        "values",
        "energy_type",
        "expected_kg",
    ),
    [
        pytest.param(
            "AAB 0 05",
            "office",
            1.0,
            17.7,
            _AAB_OFFICE,
            "electric",
            24.2,
            id="AAB-0-05",
        ),
        pytest.param(
            "AAB 0 32",
            "miscellaneous",
            1.0,
            26.99,
            _AAB_MISC,
            "electric",
            71.80,
            id="AAB-0-32",
        ),
        pytest.param(
            "AAB 0 47",
            "office",
            0.5,
            18.76,
            _AAB_OFFICE,
            "electric",
            12.83,
            id="AAB-0-47",
        ),
        pytest.param(
            "CSV 0 32",
            "libraries",
            1.0,
            34.51,
            _CSV_LIBRARIES,
            "thermal",
            367.7,
            id="CSV-0-32",
        ),
        pytest.param(
            "SOS1 0 32",
            "archives",
            0.75,
            13.94,
            _SOS1_ARCHIVES,
            "thermal",
            5.7,
            id="SOS1-0-32",
        ),
        pytest.param(
            "CCT 0 01",
            "office",
            1.0,
            36.62,
            _CCT_OFFICE,
            "electric",
            3680.37,
            id="CCT-0-01",
        ),
    ],
)
def test_building_room_reference_example(
    room_name: str,
    room_type: str,
    ratio: float,
    surface: float,
    values: dict,
    energy_type: str,
    expected_kg: float,
) -> None:
    # surface comes from the rooms reference via pre_compute.
    ctx = {
        "room_name": room_name,
        "room_type": room_type,
        "room_allocation_ratio": ratio,
        "room_surface_square_meter": surface,
    }
    kg = compute_kg_co2eq(
        BuildingRoomModuleHandler(),
        DataEntryTypeEnum.building,
        ctx,
        values,
        factor=_RoomFactor(classification={"energy_type": energy_type}),
    )
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)
