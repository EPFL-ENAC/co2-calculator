"""Unit tests for DataEntryEmissionService - emission calculation formulas."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.services.data_entry_emission_service import (
    DataEntryEmissionService,
    compute_external_ai,
    compute_external_clouds,
    compute_scientific_it_other,
    compute_trips,
)

# ======================================================================
# External Clouds Emission Calculation Tests
# ======================================================================


@pytest.mark.asyncio
async def test_compute_external_clouds_valid_calculation():
    """Test external clouds emission calculation with valid inputs."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    # Create data entry with spending
    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_clouds
    data_entry.data = {"spending": 1000.0}

    # Create factor with emission intensity
    factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.external_clouds,
        values={"factor_kgco2_per_eur": 0.144},
        classification={"kind": "calcul"},
    )

    result = await compute_external_clouds(service, data_entry, [factor])

    # 1000 EUR * 0.144 kg/EUR = 144 kg CO2eq
    assert result["kg_co2eq"] == 144.0


@pytest.mark.asyncio
async def test_compute_external_clouds_zero_spending():
    """Test external clouds calculation with zero spending."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_clouds
    data_entry.data = {"spending": 0}

    factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.external_clouds,
        values={"factor_kgco2_per_eur": 0.144},
        classification={"kind": "calcul"},
    )

    result = await compute_external_clouds(service, data_entry, [factor])

    assert result["kg_co2eq"] == 0


@pytest.mark.asyncio
async def test_compute_external_clouds_no_factors():
    """Test external clouds calculation with no factors returns None."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_clouds
    data_entry.data = {"spending": 1000.0}

    result = await compute_external_clouds(service, data_entry, [])

    assert result["kg_co2eq"] is None


@pytest.mark.asyncio
async def test_compute_external_clouds_missing_spending():
    """Test external clouds calculation with missing spending field."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_clouds
    data_entry.data = {}

    factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.external_clouds,
        values={"factor_kgco2_per_eur": 0.144},
        classification={"kind": "calcul"},
    )

    result = await compute_external_clouds(service, data_entry, [factor])

    # Should handle missing spending gracefully (0 * factor = 0)
    assert result["kg_co2eq"] == 0


# ======================================================================
# External AI Emission Calculation Tests
# ======================================================================


@pytest.mark.asyncio
async def test_compute_external_ai_valid_calculation():
    """Test external AI emission calculation with valid inputs."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    # Formula: (frequency * 5 * 46 * users * factor_gCO2eq) / 1000
    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_ai
    data_entry.data = {
        "frequency_use_per_day": 10,  # 10 queries per day
        "user_count": 100,  # 100 users
    }

    factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.external_ai,
        values={"factor_gCO2eq": 2.0},  # 2 g CO2 per query
        classification={"kind": "ai_provider"},
    )

    result = await compute_external_ai(service, data_entry, [factor])

    # (10 * 5 * 46 * 100 * 2.0) / 1000 = 460 kg CO2eq
    assert result["kg_co2eq"] == 460.0


@pytest.mark.asyncio
async def test_compute_external_ai_zero_users():
    """Test external AI calculation with zero users."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_ai
    data_entry.data = {
        "frequency_use_per_day": 10,
        "user_count": 0,
    }

    factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.external_ai,
        values={"factor_gCO2eq": 2.0},
        classification={"kind": "ai_provider"},
    )

    result = await compute_external_ai(service, data_entry, [factor])

    assert result["kg_co2eq"] is None


@pytest.mark.asyncio
async def test_compute_external_ai_no_factors():
    """Test external AI calculation with no factors returns None."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_ai
    data_entry.data = {
        "frequency_use_per_day": 10,
        "user_count": 100,
    }

    result = await compute_external_ai(service, data_entry, [])

    assert result["kg_co2eq"] is None


@pytest.mark.asyncio
async def test_compute_external_ai_missing_fields():
    """Test external AI calculation with missing required fields."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_ai
    data_entry.data = {}  # Missing frequency and user_count

    factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.external_ai,
        values={"factor_gCO2eq": 2.0},
        classification={"kind": "ai_provider"},
    )

    result = await compute_external_ai(service, data_entry, [factor])

    # Should handle missing fields gracefully (0 * 0 = 0)
    assert result["kg_co2eq"] is None


# ======================================================================
# Equipment (Scientific/IT/Other) Emission Calculation Tests
# ======================================================================


@pytest.mark.asyncio
async def test_compute_scientific_it_other_valid_calculation():
    """Test equipment emission calculation with valid inputs."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    # Formula: ((active_hrs * active_W + passive_hrs * standby_W) * 52)
    #  / 1000 * electricity_factor
    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.scientific
    data_entry.data = {
        "active_usage_hours": 40,  # 40 hrs/week active
        "passive_usage_hours": 128,  # 128 hrs/week standby (168 - 40)
    }

    # Equipment power factor
    equipment_factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        values={
            "active_power_w": 200,  # 200W active
            "standby_power_w": 5,  # 5W standby
        },
        classification={"kind": "equipment"},
    )

    # Electricity emission factor
    electricity_factor = Factor(
        id=2,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        values={"kgco2eq_per_kwh": 0.5},  # 0.5 kg CO2/kWh
        classification={"kind": "electricity"},
    )

    result = await compute_scientific_it_other(
        service, data_entry, [equipment_factor, electricity_factor]
    )

    # Weekly: (40*200 + 128*5) = 8640 Wh
    # Annual: 8640 * 52 / 1000 = 449.28 kWh
    # Emissions: 449.28 * 0.5 = 224.64 kg CO2eq
    assert result["kg_co2eq"] == pytest.approx(224.64, rel=0.01)
    assert result["weekly_wh"] == 8640
    assert result["annual_kwh"] == pytest.approx(449.28, rel=0.01)


@pytest.mark.asyncio
async def test_compute_scientific_it_other_missing_usage_hours():
    """Test equipment calculation with missing usage hours."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.it
    data_entry.data = {}  # Missing usage hours

    equipment_factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.it,
        values={"active_power_w": 200, "standby_power_w": 5},
        classification={"kind": "equipment"},
    )

    electricity_factor = Factor(
        id=2,
        data_entry_type_id=DataEntryTypeEnum.it,
        values={"kgco2eq_per_kwh": 0.5},
        classification={"kind": "electricity"},
    )

    result = await compute_scientific_it_other(
        service, data_entry, [equipment_factor, electricity_factor]
    )

    assert result["kg_co2eq"] is None


@pytest.mark.asyncio
async def test_compute_scientific_it_other_missing_power_values():
    """Test equipment calculation with missing power values in factor."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.other
    data_entry.data = {
        "active_usage_hours": 40,
        "passive_usage_hours": 128,
    }

    # Factor missing power values
    equipment_factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.other,
        values={},  # Missing active_power_w and standby_power_w
        classification={"kind": "equipment"},
    )

    electricity_factor = Factor(
        id=2,
        data_entry_type_id=DataEntryTypeEnum.other,
        values={"kgco2eq_per_kwh": 0.5},
        classification={"kind": "electricity"},
    )

    result = await compute_scientific_it_other(
        service, data_entry, [equipment_factor, electricity_factor]
    )

    assert result["kg_co2eq"] is None


@pytest.mark.asyncio
async def test_compute_scientific_it_other_no_factors():
    """Test equipment calculation with no factors returns None."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.scientific
    data_entry.data = {
        "active_usage_hours": 40,
        "passive_usage_hours": 128,
    }

    result = await compute_scientific_it_other(service, data_entry, [])

    assert result["kg_co2eq"] is None


@pytest.mark.asyncio
async def test_compute_scientific_it_other_missing_electricity_factor():
    """Test equipment calculation with missing electricity factor raises error."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.scientific
    data_entry.data = {
        "active_usage_hours": 40,
        "passive_usage_hours": 128,
    }

    equipment_factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        values={"active_power_w": 200, "standby_power_w": 5},
        classification={"kind": "equipment"},
    )

    # Only one factor provided (missing electricity factor)
    with pytest.raises(IndexError):
        await compute_scientific_it_other(service, data_entry, [equipment_factor])


@pytest.mark.asyncio
async def test_compute_scientific_it_other_zero_usage():
    """Test equipment calculation with zero usage hours."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.scientific
    data_entry.data = {
        "active_usage_hours": 0,
        "passive_usage_hours": 0,
    }

    equipment_factor = Factor(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        values={"active_power_w": 200, "standby_power_w": 5},
        classification={"kind": "equipment"},
    )

    electricity_factor = Factor(
        id=2,
        data_entry_type_id=DataEntryTypeEnum.scientific,
        values={"kgco2eq_per_kwh": 0.5},
        classification={"kind": "electricity"},
    )

    result = await compute_scientific_it_other(
        service, data_entry, [equipment_factor, electricity_factor]
    )

    assert result["kg_co2eq"] == 0


# ======================================================================
# Trips Emission Calculation Tests (Simplified - without DB queries)
# ======================================================================


@pytest.mark.asyncio
async def test_compute_trips_missing_origin_destination():
    """Test trips calculation with missing origin or destination."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.trips
    data_entry.data = {
        "transport_mode": "plane",
        "number_of_trips": 1,
        # Missing origin_location_id and destination_location_id
    }

    result = await compute_trips(service, data_entry, [])

    assert result["kg_co2eq"] is None
    assert result["transport_mode"] == "plane"


@pytest.mark.asyncio
async def test_compute_trips_invalid_transport_mode():
    """Test trips calculation with invalid transport mode."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.trips
    data_entry.data = {
        "transport_mode": "teleportation",  # Invalid mode
        "origin_location_id": 1,
        "destination_location_id": 2,
        "number_of_trips": 1,
    }

    result = await compute_trips(service, data_entry, [])

    assert result["kg_co2eq"] is None
    assert result["transport_mode"] is None


@pytest.mark.asyncio
async def test_compute_trips_response_structure():
    """Test that trips calculation returns proper response structure."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.trips
    data_entry.data = {
        "transport_mode": "train",
        "cabin_class": "second",
        "origin_location_id": 1,
        "destination_location_id": 2,
        "number_of_trips": 5,
    }

    service.session.execute = AsyncMock(
        return_value=MagicMock(all=MagicMock(return_value=[]))
    )

    result = await compute_trips(service, data_entry, [])

    # Verify response structure (DB query would fail, but structure should be correct)
    assert "kg_co2eq" in result
    assert "distance_km" in result
    assert "transport_mode" in result
    assert "cabin_class" in result
    assert "number_of_trips" in result
    assert "origin_location_id" in result
    assert "destination_location_id" in result
    assert result["transport_mode"] == "train"
    assert result["cabin_class"] == "second"
    assert result["number_of_trips"] == 5


# ======================================================================
# Formula Registration Tests
# ======================================================================


def test_formula_registration():
    """Test that all formulas are registered correctly."""
    formulas = DataEntryEmissionService.FORMULAS

    # Verify expected formulas are registered
    assert DataEntryTypeEnum.external_clouds in formulas
    assert DataEntryTypeEnum.external_ai in formulas
    assert DataEntryTypeEnum.scientific in formulas
    assert DataEntryTypeEnum.it in formulas
    assert DataEntryTypeEnum.other in formulas
    assert DataEntryTypeEnum.trips in formulas

    # Verify they point to the correct functions
    assert formulas[DataEntryTypeEnum.external_clouds] == compute_external_clouds
    assert formulas[DataEntryTypeEnum.external_ai] == compute_external_ai
    assert formulas[DataEntryTypeEnum.scientific] == compute_scientific_it_other
    assert formulas[DataEntryTypeEnum.it] == compute_scientific_it_other
    assert formulas[DataEntryTypeEnum.other] == compute_scientific_it_other
    assert formulas[DataEntryTypeEnum.trips] == compute_trips


# ======================================================================
# Unit Conversion Tests
# ======================================================================


@pytest.mark.asyncio
async def test_watts_to_kwh_conversion():
    """Test that Watt-hours are correctly converted to kWh."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.scientific
    data_entry.data = {
        "active_usage_hours": 1,
        "passive_usage_hours": 0,
    }

    # 1000W for 1 hour = 1000Wh = 1kWh per week
    equipment_factor = MagicMock()
    equipment_factor.values = {"active_power_w": 1000, "standby_power_w": 0}

    electricity_factor = MagicMock()
    electricity_factor.values = {"kgco2eq_per_kwh": 1.0}

    result = await compute_scientific_it_other(
        service, data_entry, [equipment_factor, electricity_factor]
    )

    # 1000Wh/week * 52 weeks / 1000 = 52 kWh/year
    assert result["annual_kwh"] == 52.0
    assert result["kg_co2eq"] == 52.0  # 52 kWh * 1.0 kg/kWh


@pytest.mark.asyncio
async def test_grams_to_kg_conversion():
    """Test that grams are correctly converted to kilograms in AI formula."""
    mock_session = MagicMock()
    service = DataEntryEmissionService(mock_session)

    data_entry = MagicMock()
    data_entry.data_entry_type = DataEntryTypeEnum.external_ai
    data_entry.data = {
        "frequency_use_per_day": 1,
        "user_count": 1,
    }

    # factor_gCO2eq is in grams, result should be in kg
    factor = MagicMock()
    factor.values = {"factor_gCO2eq": 1000.0}  # 1000 grams per query

    result = await compute_external_ai(service, data_entry, [factor])

    # (1 * 5 * 46 * 1 * 1000) / 1000 = 230 kg
    assert result["kg_co2eq"] == 230.0
