"""Unit tests for professional travel repository functions."""

from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.location import Location
from app.models.professional_travel import (
    ProfessionalTravel,
    ProfessionalTravelCreate,
    ProfessionalTravelEmission,
    ProfessionalTravelUpdate,
)
from app.models.user import GlobalScope, Role, RoleName, RoleScope, User
from app.repositories.professional_travel_repo import ProfessionalTravelRepository


@pytest_asyncio.fixture
async def test_user_admin(db_session: AsyncSession):
    """Create a test admin user."""
    user = User(
        id="test-admin-user",
        email="admin@test.com",
        display_name="Test Admin",
        provider="test",
    )
    # Set admin role with global scope
    user.roles = [Role(role=RoleName.CO2_BACKOFFICE_ADMIN, on=GlobalScope())]
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
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
        Location(
            transport_mode="train",
            name="Basel SBB",
            latitude=47.5476,
            longitude=7.5895,
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


@pytest_asyncio.fixture
async def sample_travels_with_emissions(
    db_session: AsyncSession,
    sample_locations,
    test_user_admin,
    test_user_standard,
):
    """Create sample professional travel records with emissions."""
    travels = [
        # Train travel - admin user
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="John Doe",
            origin_location_id=sample_locations[0].id,  # Zurich HB
            destination_location_id=sample_locations[1].id,  # Geneva
            departure_date=date(2024, 6, 15),
            is_round_trip=False,
            transport_mode="train",
            class_="class_1",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2024,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        ),
        # Flight travel - admin user
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="Jane Smith",
            origin_location_id=sample_locations[3].id,  # Zurich Airport
            destination_location_id=sample_locations[5].id,  # Paris CDG
            departure_date=date(2024, 7, 20),
            is_round_trip=False,
            transport_mode="flight",
            class_="business",
            number_of_trips=2,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2024,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        ),
        # Train travel - standard user (only visible to that user)
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="Bob Wilson",
            origin_location_id=sample_locations[0].id,  # Zurich HB
            destination_location_id=sample_locations[2].id,  # Basel
            departure_date=date(2024, 8, 10),
            is_round_trip=False,
            transport_mode="train",
            class_="class_2",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
            provider="manual",
            year=2024,
            created_by=test_user_standard.id,
            updated_by=test_user_standard.id,
        ),
        # Flight travel - different unit
        ProfessionalTravel(
            traveler_id=None,
            traveler_name="Alice Brown",
            origin_location_id=sample_locations[4].id,  # Geneva Airport
            destination_location_id=sample_locations[5].id,  # Paris CDG
            departure_date=date(2024, 9, 5),
            is_round_trip=False,
            transport_mode="flight",
            class_="eco",
            number_of_trips=1,
            unit_id="TEST-UNIT-2",
            provider="manual",
            year=2024,
            created_by=test_user_admin.id,
            updated_by=test_user_admin.id,
        ),
    ]

    for travel in travels:
        db_session.add(travel)
    await db_session.commit()

    # Add emissions for each travel
    for travel in travels:
        await db_session.refresh(travel)
        emission = ProfessionalTravelEmission(
            professional_travel_id=travel.id,
            distance_km=150.0,
            kg_co2eq=25.5,
            formula_version="v1",
            calculation_inputs={},
            is_current=True,
        )
        db_session.add(emission)

    await db_session.commit()

    return travels


class TestGetTravels:
    """Tests for get_travels function."""

    @pytest.mark.asyncio
    async def test_get_all_travels(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test getting all travels for admin user."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_admin,
            limit=100,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )

        # Admin should see all travels in TEST-UNIT-1 (3 travels)
        assert total == 3
        assert len(result) == 3
        for travel in result:
            assert isinstance(travel, ProfessionalTravel)
            assert travel.unit_id == "TEST-UNIT-1"
            assert travel.year == 2024

    @pytest.mark.asyncio
    async def test_filter_by_unit_id(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test filtering travels by unit_id."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-2",
            year=2024,
            user=test_user_admin,
            limit=100,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )

        assert total == 1
        assert len(result) == 1
        assert result[0].unit_id == "TEST-UNIT-2"

    @pytest.mark.asyncio
    async def test_filter_by_year(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test filtering travels by year."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-1",
            year=2025,  # Different year
            user=test_user_admin,
            limit=100,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )

        assert total == 0
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_standard_user_sees_only_own_travels(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_standard,
    ):
        """Test that standard users only see their own travels."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_standard,
            limit=100,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )

        # Standard user should only see 1 travel (their own)
        assert total == 1
        assert len(result) == 1
        assert result[0].created_by == test_user_standard.id
        assert result[0].traveler_name == "Bob Wilson"

    @pytest.mark.asyncio
    async def test_pagination_limit(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test pagination with limit."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_admin,
            limit=2,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )

        assert total == 3  # Total count
        assert len(result) == 2  # Limited to 2

    @pytest.mark.asyncio
    async def test_pagination_offset(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test pagination with offset."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_admin,
            limit=2,
            offset=2,
            sort_by="id",
            sort_order="asc",
        )

        assert total == 3
        assert len(result) == 1  # Only 1 item left after offset

    @pytest.mark.asyncio
    async def test_sorting_asc(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test sorting in ascending order."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_admin,
            limit=100,
            offset=0,
            sort_by="traveler_name",
            sort_order="asc",
        )

        names = [travel.traveler_name for travel in result]
        assert names == sorted(names)

    @pytest.mark.asyncio
    async def test_sorting_desc(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test sorting in descending order."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_admin,
            limit=100,
            offset=0,
            sort_by="traveler_name",
            sort_order="desc",
        )

        names = [travel.traveler_name for travel in result]
        assert names == sorted(names, reverse=True)

    @pytest.mark.asyncio
    async def test_empty_result(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test query with no matching results."""
        repo = ProfessionalTravelRepository(db_session)
        result, total = await repo.get_travels(
            unit_id="NONEXISTENT",
            year=2024,
            user=test_user_admin,
            limit=100,
            offset=0,
            sort_by="id",
            sort_order="asc",
        )

        assert total == 0
        assert len(result) == 0


class TestGetTravelById:
    """Tests for get_by_id function."""

    @pytest.mark.asyncio
    async def test_get_travel_by_id(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test getting a travel by ID."""
        repo = ProfessionalTravelRepository(db_session)
        travel = sample_travels_with_emissions[0]

        result = await repo.get_by_id(travel.id, test_user_admin)

        assert result is not None
        assert result.id == travel.id
        assert result.traveler_name == travel.traveler_name

    @pytest.mark.asyncio
    async def test_get_travel_by_id_not_found(
        self,
        db_session: AsyncSession,
        test_user_admin,
    ):
        """Test getting non-existent travel."""
        repo = ProfessionalTravelRepository(db_session)

        result = await repo.get_by_id(99999, test_user_admin)

        assert result is None

    @pytest.mark.asyncio
    async def test_standard_user_cannot_access_other_travels(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_standard,
    ):
        """Test that standard users cannot access other users' travels."""
        repo = ProfessionalTravelRepository(db_session)
        # Get a travel created by admin
        admin_travel = [
            t
            for t in sample_travels_with_emissions
            if t.created_by != test_user_standard.id
        ][0]

        result = await repo.get_by_id(admin_travel.id, test_user_standard)

        assert result is None  # Should not be accessible


class TestCreateTravel:
    """Tests for create_travel function."""

    @pytest.mark.asyncio
    async def test_create_single_travel(
        self,
        db_session: AsyncSession,
        sample_locations,
        test_user_admin,
    ):
        """Test creating a single travel record."""
        repo = ProfessionalTravelRepository(db_session)

        travel_data = ProfessionalTravelCreate(
            traveler_id=None,
            traveler_name="New Traveler",
            origin_location_id=sample_locations[0].id,
            destination_location_id=sample_locations[1].id,
            departure_date=date(2024, 11, 1),
            is_round_trip=False,
            transport_mode="train",
            class_="class_1",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
        )

        result = await repo.create_travel(
            data=travel_data,
            provider_source="manual",
            user_id=test_user_admin.id,
        )

        assert isinstance(result, ProfessionalTravel)
        assert result.traveler_name == "New Traveler"
        assert result.provider == "manual"
        assert result.created_by == test_user_admin.id
        assert result.year == 2024
        assert result.is_round_trip is False

    @pytest.mark.asyncio
    async def test_create_round_trip(
        self,
        db_session: AsyncSession,
        sample_locations,
        test_user_admin,
    ):
        """Test creating a round trip (creates 2 records)."""
        repo = ProfessionalTravelRepository(db_session)

        travel_data = ProfessionalTravelCreate(
            traveler_id=None,
            traveler_name="Round Trip Traveler",
            origin_location_id=sample_locations[0].id,
            destination_location_id=sample_locations[1].id,
            departure_date=date(2024, 12, 1),
            is_round_trip=True,
            transport_mode="train",
            class_="class_1",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
        )

        result = await repo.create_travel(
            data=travel_data,
            provider_source="manual",
            user_id=test_user_admin.id,
        )

        assert isinstance(result, list)
        assert len(result) == 2

        # Check outbound trip
        outbound = result[0]
        assert outbound.origin_location_id == sample_locations[0].id
        assert outbound.destination_location_id == sample_locations[1].id
        assert outbound.is_round_trip is False

        # Check return trip (swapped origin/destination)
        return_trip = result[1]
        assert return_trip.origin_location_id == sample_locations[1].id
        assert return_trip.destination_location_id == sample_locations[0].id
        assert return_trip.is_round_trip is False

    @pytest.mark.asyncio
    async def test_create_travel_without_departure_date(
        self,
        db_session: AsyncSession,
        sample_locations,
        test_user_admin,
    ):
        """Test creating travel without departure_date (uses current year)."""
        repo = ProfessionalTravelRepository(db_session)

        travel_data = ProfessionalTravelCreate(
            traveler_id=None,
            traveler_name="No Date Traveler",
            origin_location_id=sample_locations[0].id,
            destination_location_id=sample_locations[1].id,
            departure_date=None,
            is_round_trip=False,
            transport_mode="train",
            class_="class_1",
            number_of_trips=1,
            unit_id="TEST-UNIT-1",
        )

        result = await repo.create_travel(
            data=travel_data,
            provider_source="manual",
            user_id=test_user_admin.id,
        )

        assert isinstance(result, ProfessionalTravel)
        current_year = datetime.now(timezone.utc).year
        assert result.year == current_year


class TestUpdateTravel:
    """Tests for update_travel function."""

    @pytest.mark.asyncio
    async def test_update_travel(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test updating a travel record."""
        repo = ProfessionalTravelRepository(db_session)
        travel = sample_travels_with_emissions[0]

        update_data = ProfessionalTravelUpdate(
            traveler_name="Updated Name",
            number_of_trips=3,
        )

        result = await repo.update_travel(
            travel_id=travel.id,
            data=update_data,
            user_id=test_user_admin.id,
            user=test_user_admin,
        )

        assert result is not None
        assert result.id == travel.id
        assert result.traveler_name == "Updated Name"
        assert result.number_of_trips == 3
        assert result.updated_by == test_user_admin.id

    @pytest.mark.asyncio
    async def test_update_travel_departure_date_recalculates_year(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test that updating departure_date recalculates year."""
        repo = ProfessionalTravelRepository(db_session)
        travel = sample_travels_with_emissions[0]

        update_data = ProfessionalTravelUpdate(
            departure_date=date(2025, 1, 15),
        )

        result = await repo.update_travel(
            travel_id=travel.id,
            data=update_data,
            user_id=test_user_admin.id,
            user=test_user_admin,
        )

        assert result is not None
        assert result.departure_date == date(2025, 1, 15)
        assert result.year == 2025

    @pytest.mark.asyncio
    async def test_update_travel_not_found(
        self,
        db_session: AsyncSession,
        test_user_admin,
    ):
        """Test updating non-existent travel."""
        repo = ProfessionalTravelRepository(db_session)

        update_data = ProfessionalTravelUpdate(traveler_name="Updated Name")

        result = await repo.update_travel(
            travel_id=99999,
            data=update_data,
            user_id=test_user_admin.id,
            user=test_user_admin,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_update_travel_partial_fields(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test updating only some fields."""
        repo = ProfessionalTravelRepository(db_session)
        travel = sample_travels_with_emissions[0]
        original_transport_mode = travel.transport_mode

        update_data = ProfessionalTravelUpdate(
            number_of_trips=5,
        )

        result = await repo.update_travel(
            travel_id=travel.id,
            data=update_data,
            user_id=test_user_admin.id,
            user=test_user_admin,
        )

        assert result is not None
        assert result.number_of_trips == 5
        # Other fields should remain unchanged
        assert result.transport_mode == original_transport_mode


class TestDeleteTravel:
    """Tests for delete_travel function."""

    @pytest.mark.asyncio
    async def test_delete_travel(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test deleting a travel record."""
        repo = ProfessionalTravelRepository(db_session)
        travel = sample_travels_with_emissions[0]
        travel_id = travel.id

        result = await repo.delete_travel(travel_id, test_user_admin)

        assert result is True

        # Verify it's deleted
        deleted = await repo.get_by_id(travel_id, test_user_admin)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_delete_travel_not_found(
        self,
        db_session: AsyncSession,
        test_user_admin,
    ):
        """Test deleting non-existent travel."""
        repo = ProfessionalTravelRepository(db_session)

        result = await repo.delete_travel(99999, test_user_admin)

        assert result is False


class TestGetSummaryStats:
    """Tests for get_summary_stats function."""

    @pytest.mark.asyncio
    async def test_summary_stats_all_travels(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test getting summary statistics for all travels."""
        repo = ProfessionalTravelRepository(db_session)

        summary = await repo.get_summary_stats(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_admin,
        )

        assert "total_items" in summary
        assert "total_kg_co2eq" in summary
        assert "total_distance_km" in summary
        assert isinstance(summary["total_items"], int)
        assert isinstance(summary["total_kg_co2eq"], float)
        assert isinstance(summary["total_distance_km"], float)
        assert summary["total_items"] == 3  # 3 travels in TEST-UNIT-1

    @pytest.mark.asyncio
    async def test_summary_stats_aggregation(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test that aggregation values are correct."""
        repo = ProfessionalTravelRepository(db_session)

        summary = await repo.get_summary_stats(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_admin,
        )

        # Each travel has 150.0 km and 25.5 kg CO2eq
        # 3 travels = 450.0 km and 76.5 kg CO2eq
        assert summary["total_distance_km"] == 450.0
        assert summary["total_kg_co2eq"] == 76.5

    @pytest.mark.asyncio
    async def test_summary_stats_filter_by_unit(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test summary filtered by unit_id."""
        repo = ProfessionalTravelRepository(db_session)

        summary = await repo.get_summary_stats(
            unit_id="TEST-UNIT-2",
            year=2024,
            user=test_user_admin,
        )

        assert summary["total_items"] == 1  # 1 travel in TEST-UNIT-2

    @pytest.mark.asyncio
    async def test_summary_stats_standard_user(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_standard,
    ):
        """Test summary for standard user (only sees own travels)."""
        repo = ProfessionalTravelRepository(db_session)

        summary = await repo.get_summary_stats(
            unit_id="TEST-UNIT-1",
            year=2024,
            user=test_user_standard,
        )

        assert summary["total_items"] == 1  # Only 1 travel for standard user

    @pytest.mark.asyncio
    async def test_summary_stats_empty_result(
        self,
        db_session: AsyncSession,
        sample_travels_with_emissions,
        test_user_admin,
    ):
        """Test summary with no matching travels."""
        repo = ProfessionalTravelRepository(db_session)

        summary = await repo.get_summary_stats(
            unit_id="NONEXISTENT",
            year=2024,
            user=test_user_admin,
        )

        assert summary["total_items"] == 0
        assert summary["total_kg_co2eq"] == 0.0
        assert summary["total_distance_km"] == 0.0
