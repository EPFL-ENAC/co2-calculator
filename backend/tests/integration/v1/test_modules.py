"""Integration tests for modules API endpoints."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user
from app.main import app
from app.models.emission_factor import EmissionFactor
from app.models.equipment import Equipment, EquipmentEmission
from app.models.user import User


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.is_active = True
    user.roles = []  # Make roles iterable
    return user


@pytest.fixture
def mock_current_user(mock_user):
    """Mock the get_current_active_user dependency."""

    async def override_get_current_active_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    yield mock_user
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_permission_check(monkeypatch):
    """Mock OPA permission check to always allow for tests."""

    async def mock_query_policy(*args, **kwargs):
        return {"allow": True}

    monkeypatch.setattr("app.api.v1.modules.query_policy", mock_query_policy)


@pytest.fixture
async def emission_factor(db_session: AsyncSession):
    """Create an emission factor for testing."""
    factor = EmissionFactor(
        factor_name="swiss_electricity_mix",
        value=0.125,
        version=1,
        valid_from=datetime(2024, 1, 1),
        valid_to=None,
        region="CH",
        source="Test data",
        factor_metadata={},
    )
    db_session.add(factor)
    await db_session.commit()
    await db_session.refresh(factor)
    return factor


@pytest.fixture
async def power_factors(db_session: AsyncSession):
    """Create power factors for testing."""
    from app.models.emission_factor import PowerFactor

    # Create power factors for the equipment classes used in tests
    factors = [
        PowerFactor(
            submodule="scientific",
            equipment_class="Laboratory",
            sub_class="Microscope",
            active_power_w=200.0,
            standby_power_w=20.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data",
            power_metadata={},
        ),
        PowerFactor(
            submodule="scientific",
            equipment_class="Laboratory",
            sub_class="Advanced Microscope",
            active_power_w=250.0,
            standby_power_w=30.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data",
            power_metadata={},
        ),
    ]

    for factor in factors:
        db_session.add(factor)

    await db_session.commit()

    for factor in factors:
        await db_session.refresh(factor)

    return factors


@pytest.fixture
async def sample_equipment(
    db_session: AsyncSession, emission_factor: EmissionFactor, power_factors
):
    """Create sample equipment and emissions for testing."""
    equipment_data = []

    # Create equipment for different submodules
    for i, submodule in enumerate(["scientific", "it", "other"]):
        for j in range(3):
            equipment = Equipment(
                cost_center="C1348",
                unit_id="C1348",
                name=f"Test Equipment {submodule} {j + 1}",
                category=f"Category {submodule}",
                submodule=submodule,
                equipment_class=f"Class {submodule}",
                sub_class=f"SubClass {j}",
                active_usage_pct=50.0,
                passive_usage_pct=10.0,
                power_factor_id=power_factors[0].id,
                status="In service",
                service_date=datetime(2024, 1, 1),
            )
            db_session.add(equipment)
            equipment_data.append(equipment)

    await db_session.commit()

    # Refresh to get IDs
    for equipment in equipment_data:
        await db_session.refresh(equipment)

    # Create emissions for each equipment
    for equipment in equipment_data:
        emission = EquipmentEmission(
            equipment_id=equipment.id,
            annual_kwh=876.0,  # (100W * 50% * 8760h + 10W * 10% * 8760h) / 1000
            kg_co2eq=109.5,  # 876 kWh * 0.125 kg CO2/kWh
            emission_factor_id=emission_factor.id,
            formula_version="v1_linear",
            is_current=True,
            calculation_inputs={},
            computed_at=datetime(2024, 6, 1),  # Set to 2024 for year filtering
        )
        db_session.add(emission)

    await db_session.commit()

    return equipment_data


@pytest.mark.asyncio
async def test_get_module_success(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting module data successfully."""
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption"
    )

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert data["module_type"] == "equipment-electric-consumption"
    assert data["unit"] == "kWh"
    assert data["year"] == 2024
    assert "retrieved_at" in data
    assert "submodules" in data
    assert "totals" in data

    # Check submodules
    submodules = data["submodules"]
    assert "scientific" in submodules
    assert "it" in submodules
    assert "other" in submodules

    # Check totals
    totals = data["totals"]
    assert totals["total_submodules"] == 3
    assert totals["total_items"] == 9  # 3 items per submodule
    assert totals["total_annual_consumption_kwh"] > 0
    assert totals["total_kg_co2eq"] > 0


@pytest.mark.asyncio
async def test_get_module_with_preview_limit(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting module data with preview limit."""
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption",
        params={"preview_limit": 2},
    )

    assert response.status_code == 200
    data = response.json()

    # Check that each submodule has at most 2 items
    for submodule_id, submodule in data["submodules"].items():
        assert len(submodule["items"]) <= 2
        if submodule["count"] > 2:
            assert submodule["has_more"] is True


@pytest.mark.asyncio
async def test_get_module_invalid_preview_limit(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting module data with invalid preview limit (> 100)."""
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption",
        params={"preview_limit": 150},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_module_no_data(client: AsyncClient, mock_current_user):
    """Test getting module data when no equipment exists."""
    response = await client.get(
        "/api/v1/modules/NONEXISTENT/2024/equipment-electric-consumption"
    )

    assert response.status_code == 200
    data = response.json()

    # Should return empty submodules with zero totals
    totals = data["totals"]
    assert totals["total_items"] == 0
    assert totals["total_annual_consumption_kwh"] == 0
    assert totals["total_kg_co2eq"] == 0


@pytest.mark.asyncio
async def test_get_submodule_success(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting submodule data successfully."""
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/scientific"
    )

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert data["id"] == "scientific"
    assert data["name"] == "Scientific"
    assert data["count"] == 3
    assert len(data["items"]) == 3
    assert "summary" in data
    assert data["has_more"] is False

    # Check items structure
    for item in data["items"]:
        assert "name" in item
        assert "category" in item
        assert "submodule" in item
        assert item["submodule"] == "scientific"
        assert "equipment_class" in item
        assert "kg_co2eq" in item
        assert "annual_kwh" in item


@pytest.mark.asyncio
async def test_get_submodule_with_pagination(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting submodule data with pagination."""
    # Page 1
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/scientific",
        params={"page": 1, "limit": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["count"] == 3
    assert data["has_more"] is True

    # Page 2
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/scientific",
        params={"page": 2, "limit": 2},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1  # Only 1 item left
    assert data["count"] == 3
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_get_submodule_invalid_id(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting submodule with invalid ID format."""
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/invalid_format"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_get_submodule_nonexistent(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting non-existent submodule."""
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/sub_nonexistent"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_create_equipment_success(
    client: AsyncClient, mock_current_user, power_factors
):
    """Test creating equipment successfully."""
    equipment_data = {
        "unit_id": "C1348",
        "cost_center": "C1348",
        "name": "New Test Equipment",
        "category": "Scientific Equipment",
        "submodule": "scientific",
        "equipment_class": "Laboratory",
        "sub_class": "Microscope",
        "act_usage": 75.0,
        "pas_usage": 25.0,
        "power_factor_id": power_factors[0].id,
        "status": "In service",
    }

    response = await client.post(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment",
        json=equipment_data,
    )

    assert response.status_code == 201
    data = response.json()

    # Check returned data
    assert data["name"] == "New Test Equipment"
    assert data["unit_id"] == "C1348"
    assert data["category"] == "Scientific Equipment"
    assert data["submodule"] == "scientific"
    assert data["equipment_class"] == "Laboratory"
    assert data["sub_class"] == "Microscope"
    assert data["act_usage"] == 75.0
    assert data["pas_usage"] == 25.0
    assert data["status"] == "In service"
    assert data["created_by"] == "test-user-123"
    assert data["updated_by"] == "test-user-123"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_equipment_invalid_submodule(
    client: AsyncClient, mock_current_user
):
    """Test creating equipment with invalid submodule."""
    equipment_data = {
        "unit_id": "C1348",
        "name": "Test Equipment",
        "category": "Test Category",
        "submodule": "scientific",
        "equipment_class": "Test Class",
    }

    response = await client.post(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/invalid_submodule",
        json=equipment_data,
    )
    assert response.status_code == 422  #


@pytest.mark.asyncio
async def test_create_equipment_missing_required_fields(
    client: AsyncClient, mock_current_user
):
    """Test creating equipment with missing required fields."""
    equipment_data = {
        # "unit_id": "C1348",
        "name": "Test Equipment",
        # Missing category, submodule, equipment_class
    }

    response = await client.post(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment",
        json=equipment_data,
    )

    assert response.status_code == 400  # Validation error


@pytest.mark.asyncio
async def test_create_equipment_invalid_usage_percentage(
    client: AsyncClient, mock_current_user
):
    """Test creating equipment with invalid usage percentage."""
    equipment_data = {
        "unit_id": "C1348",
        "name": "Test Equipment22",
        "category": "Test Category",
        "submodule": "scientific",
        "equipment_class": "Test Class",
        "act_usage": 150.0,  # Invalid: > 100
    }

    response = await client.post(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/scientific",
        json=equipment_data,
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_get_equipment_success(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test getting equipment by ID successfully."""
    equipment = sample_equipment[0]

    response = await client.get(
        f"/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment/{equipment.id}"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == equipment.id
    assert data["name"] == equipment.name
    assert data["unit_id"] == equipment.unit_id
    assert data["category"] == equipment.category
    assert data["submodule"] == equipment.submodule


@pytest.mark.asyncio
async def test_get_equipment_not_found(client: AsyncClient, mock_current_user):
    """Test getting non-existent equipment."""
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment/999999"
    )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


@pytest.mark.asyncio
async def test_update_equipment_success(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test updating equipment successfully."""
    equipment = sample_equipment[0]

    update_data = {
        "name": "Updated Equipment Name",
        "act_usage": 80.0,
        "pas_usage": 20.0,
        "status": "Maintenance",
    }

    response = await client.patch(
        f"/api/v1/modules/C1348/2024/equipment-electric-consumption/scientific/{equipment.id}",
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == equipment.id
    assert data["name"] == "Updated Equipment Name"
    assert data["act_usage"] == 80.0
    assert data["pas_usage"] == 20.0
    assert data["status"] == "Maintenance"
    assert data["updated_by"] == "test-user-123"
    # Original fields should remain unchanged
    assert data["unit_id"] == equipment.unit_id
    assert data["category"] == equipment.category


@pytest.mark.asyncio
async def test_update_equipment_partial(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test partial update of equipment."""
    equipment = sample_equipment[0]

    update_data = {"name": "Partially Updated Name"}

    response = await client.patch(
        f"/api/v1/modules/C1348/2024/equipment-electric-consumption/scientific/{equipment.id}",
        json=update_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == "Partially Updated Name"
    # Other fields should remain unchanged
    assert data["category"] == equipment.category
    assert data["submodule"] == equipment.submodule


@pytest.mark.asyncio
async def test_update_equipment_not_found(client: AsyncClient, mock_current_user):
    """Test updating non-existent equipment."""
    update_data = {"name": "Updated Name"}

    response = await client.patch(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment/999999",
        json=update_data,
    )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


@pytest.mark.asyncio
async def test_update_equipment_invalid_submodule(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test updating equipment with invalid submodule."""
    equipment = sample_equipment[0]

    update_data = {"submodule": "invalid_submodule"}

    response = await client.patch(
        f"/api/v1/modules/C1348/2024/equipment-electric-consumption/invalid_submodule/{equipment.id}",
        json=update_data,
    )

    assert response.status_code == 400  # Validation error


@pytest.mark.asyncio
async def test_delete_equipment_success(
    client: AsyncClient, mock_current_user, sample_equipment
):
    """Test deleting equipment successfully."""
    equipment = sample_equipment[0]

    response = await client.delete(
        f"/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment/{equipment.id}"
    )

    assert response.status_code == 204

    # Verify equipment is deleted
    get_response = await client.get(
        f"/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment/{equipment.id}"
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_equipment_not_found(client: AsyncClient, mock_current_user):
    """Test deleting non-existent equipment."""
    response = await client.delete(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment/999999"
    )

    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


@pytest.mark.asyncio
async def test_create_equipment_with_optional_fields(
    client: AsyncClient, mock_current_user, power_factors
):
    """Test creating equipment with all optional fields."""
    equipment_data = {
        "unit_id": "C1348",
        "cost_center": "C1348",
        "name": "Comprehensive Test Equipment",
        "category": "Scientific Equipment",
        "submodule": "scientific",
        "equipment_class": "Laboratory",
        "sub_class": "Advanced Microscope",
        "act_usage": 60.0,
        "pas_usage": 15.0,
        "power_factor_id": power_factors[1].id,
        "status": "In service",
        "service_date": "2024-01-15T10:00:00",
        "cost_center_description": "Équipement de test",
        "metadata": {"manufacturer": "Test Corp", "serial": "ABC123"},
    }

    response = await client.post(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption/equipment",
        json=equipment_data,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "Comprehensive Test Equipment"
    assert data["sub_class"] == "Advanced Microscope"
    assert data["cost_center_description"] == "Équipement de test"
    assert data["equipment_metadata"] == {
        "manufacturer": "Test Corp",
        "serial": "ABC123",
    }


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """Test accessing endpoints without authentication."""
    # Override to remove authentication
    app.dependency_overrides.clear()

    # This will fail because we don't have a real OAuth setup in tests
    # But we're testing that authentication is required
    response = await client.get(
        "/api/v1/modules/C1348/2024/equipment-electric-consumption"
    )

    # Should require authentication (401) or redirect to login
    assert response.status_code in [401, 403, 307]


# ==========================================
# Tests for GET /{unit_id}/{year}/totals endpoint
# ==========================================


@pytest.fixture
async def sample_professional_travel_with_emissions(
    db_session: AsyncSession, sample_equipment
):
    """Create sample professional travel records with emissions for testing."""
    from app.models.location import Location
    from app.models.professional_travel import (
        ProfessionalTravel,
        ProfessionalTravelEmission,
    )

    # Create locations
    locations = [
        Location(
            transport_mode="train",
            name="Zurich Hauptbahnhof",
            latitude=47.3782,
            longitude=8.5402,
            countrycode="CH",
        ),
        Location(
            transport_mode="train",
            name="Geneva Cornavin",
            latitude=46.2104,
            longitude=6.1427,
            countrycode="CH",
        ),
    ]

    for location in locations:
        db_session.add(location)
    await db_session.commit()

    for location in locations:
        await db_session.refresh(location)

    # Create professional travel records
    travels = [
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="Test Traveler",
            origin_location_id=locations[0].id,
            destination_location_id=locations[1].id,
            departure_date=datetime(2024, 6, 15).date(),
            is_round_trip=False,
            transport_mode="train",
            class_="class_1",
            number_of_trips=1,
            unit_id="C1348",
            provider="manual",
            year=2024,
            created_by="test-user-123",
            updated_by="test-user-123",
        ),
    ]

    for travel in travels:
        db_session.add(travel)
    await db_session.commit()

    for travel in travels:
        await db_session.refresh(travel)

    # Create emissions for professional travel
    emissions = [
        ProfessionalTravelEmission(
            professional_travel_id=travels[0].id,
            distance_km=150.0,
            kg_co2eq=5000.0,  # 5 tCO2eq
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        ),
    ]

    for emission in emissions:
        db_session.add(emission)
    await db_session.commit()

    return travels, emissions


@pytest.fixture
def mock_permission_check_selective(monkeypatch):
    """Mock OPA permission check with selective allow/deny based on module."""

    def create_mock(equipment_allowed=True, travel_allowed=True):
        async def mock_query_policy(endpoint, input_data):
            permission_path = input_data.get("path", "")
            if permission_path == "modules.equipment":
                return {"allow": equipment_allowed, "reason": "Test permission"}
            elif permission_path == "modules.professional_travel":
                return {"allow": travel_allowed, "reason": "Test permission"}
            return {"allow": True}

        monkeypatch.setattr("app.api.v1.modules.query_policy", mock_query_policy)
        return mock_query_policy

    return create_mock


@pytest.mark.asyncio
async def test_get_module_totals_success(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    sample_professional_travel_with_emissions,
):
    """Test successful aggregation with both modules accessible."""
    # Equipment: 9 items * 109.5 kg CO2eq = 985.5 kg CO2eq = 0.99 tCO2eq
    # Professional travel: 5000 kg CO2eq = 5.0 tCO2eq
    # Total: 0.99 + 5.0 = 5.99 tCO2eq

    response = await client.get("/api/v1/modules/C1348/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Check structure
    assert "total" in data
    assert "equipment-electric-consumption" in data
    assert "professional-travel" in data

    # Check values are floats
    assert isinstance(data["total"], float)
    assert isinstance(data["equipment-electric-consumption"], float)
    assert isinstance(data["professional-travel"], float)

    # Check that totals are calculated correctly
    assert data["equipment-electric-consumption"] > 0
    assert data["professional-travel"] == 5.0  # 5000 kg / 1000
    assert data["total"] == round(
        data["equipment-electric-consumption"] + data["professional-travel"], 2
    )


@pytest.mark.asyncio
async def test_get_module_totals_permission_denied_equipment(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    sample_professional_travel_with_emissions,
    monkeypatch,
):
    """Test permission denied for equipment module."""

    # Mock permission check to deny equipment but allow travel
    async def mock_query_policy(endpoint, input_data):
        permission_path = input_data.get("path", "")
        if permission_path == "modules.equipment":
            return {"allow": False, "reason": "Permission denied"}
        return {"allow": True}

    monkeypatch.setattr("app.api.v1.modules.query_policy", mock_query_policy)

    response = await client.get("/api/v1/modules/C1348/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Equipment should be 0 (permission denied)
    assert data["equipment-electric-consumption"] == 0.0
    # Professional travel should still be included
    assert data["professional-travel"] == 5.0
    # Total should only include travel
    assert data["total"] == 5.0


@pytest.mark.asyncio
async def test_get_module_totals_permission_denied_travel(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    sample_professional_travel_with_emissions,
    monkeypatch,
):
    """Test permission denied for professional travel module."""

    # Mock permission check to allow equipment but deny travel
    async def mock_query_policy(endpoint, input_data):
        permission_path = input_data.get("path", "")
        if permission_path == "modules.professional_travel":
            return {"allow": False, "reason": "Permission denied"}
        return {"allow": True}

    monkeypatch.setattr("app.api.v1.modules.query_policy", mock_query_policy)

    response = await client.get("/api/v1/modules/C1348/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Equipment should be included
    assert data["equipment-electric-consumption"] > 0
    # Professional travel should be 0 (permission denied)
    assert data["professional-travel"] == 0.0
    # Total should only include equipment
    assert data["total"] == data["equipment-electric-consumption"]


@pytest.mark.asyncio
async def test_get_module_totals_permission_denied_both(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    sample_professional_travel_with_emissions,
    monkeypatch,
):
    """Test permission denied for both modules."""

    # Mock permission check to deny both modules
    async def mock_query_policy(endpoint, input_data):
        permission_path = input_data.get("path", "")
        if permission_path in ["modules.equipment", "modules.professional_travel"]:
            return {"allow": False, "reason": "Permission denied"}
        return {"allow": True}

    monkeypatch.setattr("app.api.v1.modules.query_policy", mock_query_policy)

    response = await client.get("/api/v1/modules/C1348/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Both should be 0 (permission denied)
    assert data["equipment-electric-consumption"] == 0.0
    assert data["professional-travel"] == 0.0
    # Total should be 0
    assert data["total"] == 0.0


@pytest.mark.asyncio
async def test_get_module_totals_zero_emissions_travel(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    db_session: AsyncSession,
):
    """Test edge case where professional travel module returns zero emissions."""
    # Equipment data exists, but no travel data
    response = await client.get("/api/v1/modules/C1348/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Equipment should be included
    assert data["equipment-electric-consumption"] > 0
    # Professional travel should be 0 (no data)
    assert data["professional-travel"] == 0.0
    # Total should only include equipment
    assert data["total"] == data["equipment-electric-consumption"]


@pytest.mark.asyncio
async def test_get_module_totals_zero_emissions_both(
    client: AsyncClient,
    mock_current_user,
):
    """Test edge case where both modules return zero emissions."""
    # No data for either module
    response = await client.get("/api/v1/modules/C1348/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Both should be 0
    assert data["equipment-electric-consumption"] == 0.0
    assert data["professional-travel"] == 0.0
    # Total should be 0
    assert data["total"] == 0.0


@pytest.mark.asyncio
async def test_get_module_totals_conversion_kg_to_tonnes(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    sample_professional_travel_with_emissions,
):
    """Test that kg CO2eq is correctly converted to tonnes (tCO2eq)."""
    response = await client.get("/api/v1/modules/C1348/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Professional travel: 5000 kg CO2eq = 5.0 tCO2eq
    assert data["professional-travel"] == 5.0

    # Equipment: should be in tonnes (kg / 1000)
    # 9 items * 109.5 kg = 985.5 kg = 0.99 tCO2eq (rounded to 2 decimals)
    assert data["equipment-electric-consumption"] == round(985.5 / 1000.0, 2)

    # Total should be sum of both in tonnes
    expected_total = round(
        data["equipment-electric-consumption"] + data["professional-travel"], 2
    )
    assert data["total"] == expected_total


@pytest.mark.asyncio
async def test_get_module_totals_different_unit_id(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    sample_professional_travel_with_emissions,
):
    """Test totals for a different unit ID with no data."""
    response = await client.get("/api/v1/modules/DIFFERENT-UNIT/2024/totals")

    assert response.status_code == 200
    data = response.json()

    # Both should be 0 (no data for this unit)
    assert data["equipment-electric-consumption"] == 0.0
    assert data["professional-travel"] == 0.0
    assert data["total"] == 0.0


@pytest.mark.asyncio
async def test_get_module_totals_different_year(
    client: AsyncClient,
    mock_current_user,
    sample_equipment,
    sample_professional_travel_with_emissions,
):
    """Test totals for a different year with no data."""
    response = await client.get("/api/v1/modules/C1348/2023/totals")

    assert response.status_code == 200
    data = response.json()

    # Equipment data is for 2024, so 2023 should return 0
    # Professional travel is for 2024, so 2023 should return 0
    assert data["equipment-electric-consumption"] == 0.0
    assert data["professional-travel"] == 0.0
    assert data["total"] == 0.0
