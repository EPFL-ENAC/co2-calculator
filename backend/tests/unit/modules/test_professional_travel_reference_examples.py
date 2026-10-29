"""Professional-travel reference examples (#2771).

Planes: (great-circle km + 95) × trips × ef × rfi. Trains: great-circle km
× 1.2 × trips × ef. Rows: back-office doc, "test calculation travel_planes"
and "test calculation travel_trains". Factors: travel_planes_factors.csv,
travel_trains_factors.csv.

``distance_km`` is pre_compute's output, built here from the doc's
great-circle km. Haversine, rounding, haul bands and the train country are
pinned in tests/unit/utils/test_distance_geography.py.
"""

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.modules.professional_travel import (
    ProfessionalTravelPlaneModuleHandler,
    ProfessionalTravelTrainModuleHandler,
)
from app.utils.distance_geography import FLIGHT_APPROACH_KM, TRAIN_ROUTING_FACTOR
from tests.unit.modules.reference_examples import TOLERANCE_KG, compute_kg_co2eq


def _doc_arithmetic(actual: float) -> pytest.MarkDecorator:
    return pytest.mark.xfail(
        strict=True,
        raises=AssertionError,
        reason=f"#2771: the doc's own formula gives {actual}",
    )


@pytest.mark.parametrize(
    ("cabin_class", "great_circle_km", "trips", "ef", "expected_kg"),
    [
        pytest.param("economy", 407.6, 1, 0.2906, 197.18, id="GVA-CDG"),
        pytest.param(
            "business",
            753.7,
            2,
            0.4471,
            1024.57,
            id="GVA-LHR",
            marks=_doc_arithmetic(1024.53),
        ),
        pytest.param("economy", 459.2, 1, 0.2906, 217.41, id="GVA-FRA"),
        pytest.param("business", 6201.1, 1, 0.393, 3340.39, id="GVA-JFK"),
        pytest.param("economy", 9509.4, 1, 0.1902, 2466.12, id="GVA-LAX"),
        pytest.param(
            "business",
            5540.0,
            3,
            0.393,
            8968.97,
            id="LHR-JFK",
            marks=_doc_arithmetic(8968.95),
        ),
    ],
)
def test_plane_reference_example(
    cabin_class: str,
    great_circle_km: float,
    trips: int,
    ef: float,
    expected_kg: float,
) -> None:
    ctx = {
        "cabin_class": cabin_class,
        "distance_km": (great_circle_km + FLIGHT_APPROACH_KM) * trips,
    }
    kg = compute_kg_co2eq(
        ProfessionalTravelPlaneModuleHandler(),
        DataEntryTypeEnum.plane,
        ctx,
        {"ef_kg_co2eq_per_km": ef, "rfi_adjustment": 1.35},
    )
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)


@pytest.mark.parametrize(
    ("great_circle_km", "trips", "country_code", "ef", "expected_kg"),
    [
        pytest.param(184.9, 1, "CH", 0.00979, 2.17, id="Geneve-Basel"),
        pytest.param(374.3, 2, "DE", 0.0719, 64.59, id="Basel-Aachen"),
        pytest.param(410.6, 1, "FR", 0.0269, 13.26, id="Geneve-Paris"),
        pytest.param(630.6, 1, "DE", 0.0719, 54.41, id="Milano-Aachen"),
        pytest.param(113.0, 3, "FR", 0.0269, 10.95, id="Geneve-Lyon"),
        pytest.param(260.0, 2, "IT", 0.0491, 30.64, id="Basel-Milano"),
        pytest.param(
            980.0,
            1,
            "GB",
            0.0775,
            90.78,
            id="Geneve-London",
            marks=_doc_arithmetic(91.14),
        ),
    ],
)
def test_train_reference_example(
    great_circle_km: float,
    trips: int,
    country_code: str,
    ef: float,
    expected_kg: float,
) -> None:
    # The doc leaves cabin_class blank; the code requires first or second.
    ctx = {
        "cabin_class": "second",
        "distance_km": great_circle_km * TRAIN_ROUTING_FACTOR * trips,
        "country_code": country_code,
    }
    kg = compute_kg_co2eq(
        ProfessionalTravelTrainModuleHandler(),
        DataEntryTypeEnum.train,
        ctx,
        {"ef_kg_co2eq_per_km": ef},
    )
    assert kg == pytest.approx(expected_kg, abs=TOLERANCE_KG)
