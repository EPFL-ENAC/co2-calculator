"""Integration tests for professional travel API endpoints."""

from datetime import date
from unittest.mock import Mock

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_active_user
from app.main import app
from app.models.location import Location
from app.models.professional_travel import (
    ProfessionalTravel,
    ProfessionalTravelEmission,
)
from app.models.user import GlobalScope, Role, RoleName, RoleScope, User


@pytest.fixture
def mock_user():
    """Create a mock user for testing."""
    user = Mock(spec=User)
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.is_active = True
    user.roles = []  # Make roles iterable
    user.has_role = Mock(
        return_value=False
    )  # Mock has_role to return False (not a standard user)
    return user


@pytest.fixture
def mock_current_user(mock_user):
    """Mock the get_current_active_user dependency."""

    async def override_get_current_active_user():
        return mock_user

    app.dependency_overrides[get_current_active_user] = override_get_current_active_user
    yield mock_user
    app.dependency_overrides.clear()


# Note: professional_travel endpoints don't use query_policy directly,
# they rely on service layer filtering based on user roles


@pytest.fixture
async def test_user_admin(db_session: AsyncSession):
    """Create a test admin user."""
    user = User(
        id="test-admin-user",
        email="admin@test.com",
        display_name="Test Admin",
        provider="test",
    )
    # Set admin role with global scope
    user.roles = [Role(role=RoleName.CO2_SUPERADMIN, on=GlobalScope())]
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_standard(db_session: AsyncSession):
    """Create a test standard user."""
    user = User(
        id="test-standard-user",
        email="user@test.com",
        display_name="Test User",
        provider="test",
    )
    # Set standard user role with unit scope
    user.roles = [Role(role=RoleName.CO2_USER_STD, on=RoleScope(unit="TEST-UNIT-1"))]
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_locations(db_session: AsyncSession):
    """Create sample locations (train stations and airports)."""
    locations = [
        # Train stations
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
        # Airports
        Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            countrycode="CH",
        ),
        Location(
            transport_mode="plane",
            name="Geneva Airport",
            latitude=46.2380,
            longitude=6.1090,
            iata_code="GVA",
            countrycode="CH",
        ),
        Location(
            transport_mode="plane",
            name="Paris Charles de Gaulle",
            latitude=49.0097,
            longitude=2.5479,
            iata_code="CDG",
            countrycode="FR",
        ),
    ]

    for location in locations:
        db_session.add(location)
    await db_session.commit()

    for location in locations:
        await db_session.refresh(location)

    return locations


@pytest.fixture
async def sample_travels_with_emissions(
    db_session: AsyncSession,
    sample_locations,
    test_user_admin,
):
    """Create sample professional travel records with emissions for testing."""
    travels = [
        # Train travel - 2023
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="John Doe",
            origin_location_id=sample_locations[0].id,  # Zurich HB
            destination_location_id=sample_locations[1].id,  # Geneva
            departure_date=date(2023, 6, 15),
            is_round_trip=False,
            transport_mode="train",
            class_="class_1",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2023,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        ),
        # Flight travel - 2023
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="Jane Smith",
            origin_location_id=sample_locations[2].id,  # Zurich Airport
            destination_location_id=sample_locations[4].id,  # Paris CDG
            departure_date=date(2023, 7, 20),
            is_round_trip=True,
            transport_mode="flight",
            class_="business",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2023,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        ),
        # Train travel - 2024
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="Bob Johnson",
            origin_location_id=sample_locations[0].id,  # Zurich HB
            destination_location_id=sample_locations[1].id,  # Geneva
            departure_date=date(2024, 6, 15),
            is_round_trip=False,
            transport_mode="train",
            class_="class_2",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2024,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        ),
        # Flight travel - 2024
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="Alice Brown",
            origin_location_id=sample_locations[2].id,  # Zurich Airport
            destination_location_id=sample_locations[4].id,  # Paris CDG
            departure_date=date(2024, 8, 10),
            is_round_trip=False,
            transport_mode="flight",
            class_="eco",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2024,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        ),
    ]

    for travel in travels:
        db_session.add(travel)
    await db_session.commit()

    for travel in travels:
        await db_session.refresh(travel)

    # Create emissions for each travel
    emissions = [
        ProfessionalTravelEmission(
            professional_travel_id=travels[0].id,
            distance_km=150.0,
            kg_co2eq=50.0,
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        ),
        ProfessionalTravelEmission(
            professional_travel_id=travels[1].id,
            distance_km=1200.0,
            kg_co2eq=1500.0,
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        ),
        ProfessionalTravelEmission(
            professional_travel_id=travels[2].id,
            distance_km=120.0,
            kg_co2eq=40.0,
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        ),
        ProfessionalTravelEmission(
            professional_travel_id=travels[3].id,
            distance_km=800.0,
            kg_co2eq=800.0,
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        ),
    ]

    for emission in emissions:
        db_session.add(emission)
    await db_session.commit()

    for emission in emissions:
        await db_session.refresh(emission)

    return travels, emissions


class TestProfessionalTravelStatsByClass:
    """Test GET /professional-travel/{unit_id}/{year}/stats-by-class endpoint."""

    async def test_get_stats_by_class_success(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test successful retrieval of stats by class."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2023/stats-by-class"
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure of returned data
        for item in data:
            assert "name" in item
            assert "value" in item
            assert "children" in item
            assert isinstance(item["children"], list)
            assert item["value"] > 0

            # Check children structure
            for child in item["children"]:
                assert "name" in child
                assert "value" in child
                assert "percentage" in child
                assert child["value"] > 0
                assert 0 <= child["percentage"] <= 100

    async def test_get_stats_by_class_multiple_transport_modes(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test stats by class with multiple transport modes."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2023/stats-by-class"
        )

        assert response.status_code == 200
        data = response.json()

        # Should have both train and flight categories
        transport_modes = [item["name"] for item in data]
        assert "train" in transport_modes or "flight" in transport_modes

    async def test_get_stats_by_class_empty_year(
        self,
        client: AsyncClient,
        mock_current_user,
    ):
        """Test stats by class for year with no data."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2025/stats-by-class"
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_stats_by_class_different_years(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test stats by class for different years."""
        response_2023 = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2023/stats-by-class"
        )
        response_2024 = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2024/stats-by-class"
        )

        assert response_2023.status_code == 200
        assert response_2024.status_code == 200

        data_2023 = response_2023.json()
        data_2024 = response_2024.json()

        # Both years should have data
        assert len(data_2023) > 0
        assert len(data_2024) > 0

        # Values should be different between years
        total_2023 = sum(item["value"] for item in data_2023)
        total_2024 = sum(item["value"] for item in data_2024)

        assert total_2023 != total_2024

    async def test_get_stats_by_class_invalid_unit(
        self,
        client: AsyncClient,
        mock_current_user,
    ):
        """Test stats by class with invalid unit ID."""
        response = await client.get(
            "/api/v1/professional-travel/INVALID-UNIT/2023/stats-by-class"
        )

        assert response.status_code == 200
        data = response.json()

        # Should return empty list for non-existent unit
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_stats_by_class_percentage_calculation(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test that percentages are correctly calculated."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2023/stats-by-class"
        )

        assert response.status_code == 200
        data = response.json()

        # Check that percentages sum to approximately 100% (within rounding)
        total_percentage = 0.0
        for item in data:
            for child in item["children"]:
                total_percentage += child["percentage"]

        # Allow for small rounding differences
        assert abs(total_percentage - 100.0) < 1.0


class TestProfessionalTravelEvolutionOverTime:
    """Test GET /professional-travel/{unit_id}/evolution-over-time endpoint."""

    async def test_get_evolution_over_time_success(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test successful retrieval of evolution over time."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/evolution-over-time"
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure of returned data
        for item in data:
            assert "year" in item
            assert "transport_mode" in item
            assert "kg_co2eq" in item
            assert isinstance(item["year"], int)
            assert isinstance(item["transport_mode"], str)
            assert isinstance(item["kg_co2eq"], (int, float))
            assert item["kg_co2eq"] > 0

    async def test_get_evolution_over_time_multiple_years(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test evolution over time with multiple years."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/evolution-over-time"
        )

        assert response.status_code == 200
        data = response.json()

        # Should have data for both 2023 and 2024
        years = {item["year"] for item in data}
        assert 2023 in years
        assert 2024 in years

    async def test_get_evolution_over_time_multiple_transport_modes(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test evolution over time with multiple transport modes."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/evolution-over-time"
        )

        assert response.status_code == 200
        data = response.json()

        # Should have both train and flight data
        transport_modes = {item["transport_mode"] for item in data}
        assert "train" in transport_modes or "flight" in transport_modes

    async def test_get_evolution_over_time_empty_unit(
        self,
        client: AsyncClient,
        mock_current_user,
    ):
        """Test evolution over time for unit with no data."""
        response = await client.get(
            "/api/v1/professional-travel/EMPTY-UNIT/evolution-over-time"
        )

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) == 0

    async def test_get_evolution_over_time_aggregation(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test evolution over time aggregates by year and transport mode."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/evolution-over-time"
        )

        assert response.status_code == 200
        data = response.json()

        # Group by year and transport_mode
        grouped = {}
        for item in data:
            key = (item["year"], item["transport_mode"])
            if key not in grouped:
                grouped[key] = 0
            grouped[key] += item["kg_co2eq"]

        # Should have entries for 2023 train, 2023 flight, 2024 train, 2024 flight
        assert (2023, "train") in grouped
        assert (2023, "flight") in grouped
        assert (2024, "train") in grouped
        assert (2024, "flight") in grouped

        # Check that values match expected emissions
        assert grouped[(2023, "train")] == 50.0
        assert grouped[(2023, "flight")] == 1500.0
        assert grouped[(2024, "train")] == 40.0
        assert grouped[(2024, "flight")] == 800.0

    async def test_get_evolution_over_time_ordering(
        self,
        client: AsyncClient,
        mock_current_user,
        sample_travels_with_emissions,
    ):
        """Test that evolution over time returns data in correct order."""
        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/evolution-over-time"
        )

        assert response.status_code == 200
        data = response.json()

        # Data should be ordered by year (ascending), then transport_mode (ascending)
        for i in range(len(data) - 1):
            current = data[i]
            next_item = data[i + 1]

            # Year ascending, or if same year, transport_mode ascending
            assert current["year"] < next_item["year"] or (
                current["year"] == next_item["year"]
                and current["transport_mode"] <= next_item["transport_mode"]
            )

    async def test_get_stats_by_class_with_null_class(
        self,
        client: AsyncClient,
        mock_current_user,
        db_session: AsyncSession,
        sample_locations,
        test_user_admin,
    ):
        """Test stats by class handles null class values."""
        # Create a travel with null class
        travel = ProfessionalTravel(
            traveler_id=None,
            traveler_name="Test User",
            origin_location_id=sample_locations[0].id,
            destination_location_id=sample_locations[1].id,
            departure_date=date(2023, 1, 1),
            is_round_trip=False,
            transport_mode="flight",
            class_=None,  # Null class
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2023,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        )
        db_session.add(travel)
        await db_session.commit()
        await db_session.refresh(travel)

        # Create emission
        emission = ProfessionalTravelEmission(
            professional_travel_id=travel.id,
            distance_km=200.0,
            kg_co2eq=200.0,
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        )
        db_session.add(emission)
        await db_session.commit()

        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2023/stats-by-class"
        )

        assert response.status_code == 200
        data = response.json()

        # Should handle null class (should use default class based on transport_mode)
        assert isinstance(data, list)

    async def test_get_stats_by_class_filters_zero_emissions(
        self,
        client: AsyncClient,
        mock_current_user,
        db_session: AsyncSession,
        sample_locations,
        test_user_admin,
    ):
        """Test that stats by class filters out zero or negative emissions."""
        # Create a travel with zero emission
        travel = ProfessionalTravel(
            traveler_id=None,
            traveler_name="Test User",
            origin_location_id=sample_locations[0].id,
            destination_location_id=sample_locations[1].id,
            departure_date=date(2023, 1, 1),
            is_round_trip=False,
            transport_mode="train",
            class_="class_1",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2023,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        )
        db_session.add(travel)
        await db_session.commit()
        await db_session.refresh(travel)

        # Create emission with zero value
        emission = ProfessionalTravelEmission(
            professional_travel_id=travel.id,
            distance_km=0.0,
            kg_co2eq=0.0,  # Zero emission
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        )
        db_session.add(emission)
        await db_session.commit()

        response = await client.get(
            "/api/v1/professional-travel/TEST-UNIT-1/2023/stats-by-class"
        )

        assert response.status_code == 200
        data = response.json()

        # Zero emissions should be filtered out
        for item in data:
            assert item["value"] > 0
            for child in item["children"]:
                assert child["value"] > 0
