"""Unit tests for travel calculation service.

Tests cover:
- Distance calculation functions (haversine_distance,
  calculate_plane_distance, calculate_train_distance)
- Haul category determination (get_haul_category)
- Plane emission calculations (calculate_plane_emissions)
- Train emission calculations (calculate_train_emissions)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.location import Location
from app.models.travel_impact_factor import PlaneImpactFactor, TrainImpactFactor
from app.services.travel_calculation_service import TravelCalculationService
from app.utils.distance_geography import (
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
    haversine_distance,
)


class TestHaversineDistance:
    """Tests for haversine_distance function."""

    def test_haversine_basic(self):
        """Test basic Haversine distance calculation."""
        # Distance between Zurich and Geneva (approximately 227 km)
        result = haversine_distance(
            lat1=47.3782,
            lon1=8.5402,  # Zurich
            lat2=46.2104,
            lon2=6.1427,  # Geneva
        )

        # Should be approximately 227 km
        assert pytest.approx(result, rel=0.1) == 227.0

    def test_haversine_same_location(self):
        """Test Haversine distance for same location."""
        result = haversine_distance(
            lat1=47.3782,
            lon1=8.5402,
            lat2=47.3782,
            lon2=8.5402,
        )

        assert result == 0.0

    def test_haversine_long_distance(self):
        """Test Haversine distance for long distance (Zurich to New York)."""
        result = haversine_distance(
            lat1=47.3782,
            lon1=8.5402,  # Zurich
            lat2=40.7128,
            lon2=-74.0060,  # New York
        )

        # Should be approximately 6200 km
        assert pytest.approx(result, rel=0.1) == 6200.0

    def test_haversine_invalid_latitude(self):
        """Test Haversine distance with invalid latitude."""
        with pytest.raises(ValueError, match="Invalid latitude"):
            haversine_distance(
                lat1=91.0,
                lon1=8.5402,  # Invalid latitude
                lat2=47.3782,
                lon2=8.5402,
            )

    def test_haversine_invalid_longitude(self):
        """Test Haversine distance with invalid longitude."""
        with pytest.raises(ValueError, match="Invalid longitude"):
            haversine_distance(
                lat1=47.3782,
                lon1=181.0,  # Invalid longitude
                lat2=47.3782,
                lon2=8.5402,
            )

    @pytest.mark.parametrize(
        "lat1,lon1,lat2,lon2,expected_approx",
        [
            # Short distances
            (47.3782, 8.5402, 47.4647, 8.5492, 10.0),  # Zurich to Zurich Airport
            # Medium distances
            (47.3782, 8.5402, 46.2104, 6.1427, 227.0),  # Zurich to Geneva
            # Long distances
            (47.3782, 8.5402, 40.7128, -74.0060, 6200.0),  # Zurich to New York
        ],
    )
    def test_haversine_parametrized(self, lat1, lon1, lat2, lon2, expected_approx):
        """Test Haversine distance with various coordinates."""
        result = haversine_distance(lat1, lon1, lat2, lon2)
        assert pytest.approx(result, rel=0.1) == expected_approx


class TestCalculatePlaneDistance:
    """Tests for calculate_plane_distance function."""

    def test_plane_distance_basic(self):
        """Test basic plane distance calculation (Haversine + 95km)."""
        origin = Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            countrycode="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Geneva Airport",
            latitude=46.2380,
            longitude=6.1090,
            iata_code="GVA",
            countrycode="CH",
        )

        result = calculate_plane_distance(origin, dest)

        # Haversine distance Zurich-Geneva is ~227km, so result should be ~322km
        assert result > 227.0  # Should be greater than Haversine
        assert pytest.approx(result, rel=0.1) == 322.0  # 227 + 95

    def test_plane_distance_same_location(self):
        """Test plane distance for same location."""
        origin = Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            countrycode="CH",
        )

        result = calculate_plane_distance(origin, origin)

        # Should be 0 + 95 = 95 km
        assert result == 95.0


class TestCalculateTrainDistance:
    """Tests for calculate_train_distance function."""

    def test_train_distance_basic(self):
        """Test basic train distance calculation (Haversine * 1.2)."""
        origin = Location(
            transport_mode="train",
            name="Zurich Hauptbahnhof",
            latitude=47.3782,
            longitude=8.5402,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Geneva Cornavin",
            latitude=46.2104,
            longitude=6.1427,
            countrycode="CH",
        )

        result = calculate_train_distance(origin, dest)

        # Haversine distance Zurich-Geneva is ~227km, so result should be ~272km
        assert result > 227.0  # Should be greater than Haversine
        assert pytest.approx(result, rel=0.1) == 272.0  # 227 * 1.2

    def test_train_distance_same_location(self):
        """Test train distance for same location."""
        origin = Location(
            transport_mode="train",
            name="Zurich Hauptbahnhof",
            latitude=47.3782,
            longitude=8.5402,
            countrycode="CH",
        )

        result = calculate_train_distance(origin, origin)

        # Should be 0 * 1.2 = 0 km
        assert result == 0.0

    def test_train_distance_multiplier(self):
        """Test that train distance uses 1.2 multiplier correctly."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            countrycode="CH",
        )

        haversine_dist = haversine_distance(
            origin.latitude, origin.longitude, dest.latitude, dest.longitude
        )
        train_dist = calculate_train_distance(origin, dest)

        # Train distance should be exactly 1.2 times Haversine
        assert pytest.approx(train_dist, rel=0.01) == haversine_dist * 1.2


class TestGetHaulCategory:
    """Tests for get_haul_category function."""

    def test_very_short_haul(self):
        """Test very short haul category (< 800 km)."""
        assert get_haul_category(500.0) == "very_short_haul"
        assert get_haul_category(799.9) == "very_short_haul"
        assert get_haul_category(0.0) == "very_short_haul"

    def test_short_haul(self):
        """Test short haul category (800-1500 km)."""
        assert get_haul_category(800.0) == "short_haul"
        assert get_haul_category(1000.0) == "short_haul"
        assert get_haul_category(1499.9) == "short_haul"

    def test_medium_haul(self):
        """Test medium haul category (1500-4000 km)."""
        assert get_haul_category(1500.0) == "medium_haul"
        assert get_haul_category(2500.0) == "medium_haul"
        assert get_haul_category(3999.9) == "medium_haul"

    def test_long_haul(self):
        """Test long haul category (> 4000 km)."""
        assert get_haul_category(4000.0) == "long_haul"
        assert get_haul_category(10000.0) == "long_haul"
        assert get_haul_category(15000.0) == "long_haul"

    @pytest.mark.parametrize(
        "distance,category",
        [
            (100, "very_short_haul"),
            (500, "very_short_haul"),
            (800, "short_haul"),
            (1200, "short_haul"),
            (1500, "medium_haul"),
            (3000, "medium_haul"),
            (4000, "long_haul"),
            (8000, "long_haul"),
        ],
    )
    def test_haul_category_parametrized(self, distance, category):
        """Test haul category with various distances."""
        assert get_haul_category(distance) == category


class TestCalculatePlaneEmissions:
    """Tests for calculate_plane_emissions function."""

    @pytest_asyncio.fixture
    async def mock_session(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest_asyncio.fixture
    async def sample_airports(self):
        """Create sample airport locations."""
        origin = Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            countrycode="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Geneva Airport",
            latitude=46.2380,
            longitude=6.1090,
            iata_code="GVA",
            countrycode="CH",
        )
        return origin, dest

    @pytest_asyncio.fixture
    async def mock_short_haul_factor(self, mock_session):
        """Create a mock short haul impact factor."""
        factor = PlaneImpactFactor(
            category="short_haul",
            impact_score=0.25,
            rfi_adjustment=1.0,
            valid_from=None,
            valid_to=None,
        )
        # Mock the query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor
        mock_session.execute.return_value = mock_result
        return factor

    @pytest.mark.asyncio
    async def test_calculate_plane_emissions_basic(
        self, mock_session, sample_airports, mock_short_haul_factor
    ):
        """Test basic plane emissions calculation."""
        origin, dest = sample_airports
        service = TravelCalculationService(mock_session)

        distance_km, kg_co2eq = await service.calculate_plane_emissions(
            origin_airport=origin,
            dest_airport=dest,
            class_="eco",
            number_of_trips=1,
        )

        # Distance should be Haversine + 95km (~322km)
        assert distance_km > 300.0
        # CO2 should be: distance × impact_score × rfi_adjustment × trips
        # ~322 × 0.25 × 1.0 × 1 = ~80.5
        assert kg_co2eq > 0.0
        assert pytest.approx(kg_co2eq, rel=0.1) == 80.5

    @pytest.mark.asyncio
    async def test_calculate_plane_emissions_multiple_trips(
        self, mock_session, sample_airports, mock_short_haul_factor
    ):
        """Test plane emissions with multiple trips."""
        origin, dest = sample_airports
        service = TravelCalculationService(mock_session)

        distance_km, kg_co2eq = await service.calculate_plane_emissions(
            origin_airport=origin,
            dest_airport=dest,
            class_="eco",
            number_of_trips=3,
        )

        # Distance should be the same
        assert distance_km > 300.0
        # CO2 should be 3x (trips multiplier)
        distance_km_single, kg_co2eq_single = await service.calculate_plane_emissions(
            origin_airport=origin,
            dest_airport=dest,
            class_="eco",
            number_of_trips=1,
        )
        assert pytest.approx(kg_co2eq, rel=0.01) == kg_co2eq_single * 3

    @pytest.mark.asyncio
    async def test_calculate_plane_emissions_different_haul_categories(
        self, mock_session
    ):
        """Test plane emissions for different haul categories."""
        # Very short haul
        origin_vsh = Location(
            transport_mode="plane",
            name="Airport A",
            latitude=47.0,
            longitude=8.0,
            iata_code="AAA",
            countrycode="CH",
        )
        dest_vsh = Location(
            transport_mode="plane",
            name="Airport B",
            latitude=47.5,
            longitude=8.5,
            iata_code="BBB",
            countrycode="CH",
        )

        factor_vsh = PlaneImpactFactor(
            category="very_short_haul",
            impact_score=0.3,
            rfi_adjustment=1.0,
        )
        mock_result_vsh = MagicMock()
        mock_result_vsh.scalar_one_or_none.return_value = factor_vsh
        mock_session.execute.return_value = mock_result_vsh

        service = TravelCalculationService(mock_session)
        distance, kg_co2eq = await service.calculate_plane_emissions(
            origin_airport=origin_vsh,
            dest_airport=dest_vsh,
            class_="eco",
            number_of_trips=1,
        )

        assert distance < 800.0  # Should be very short haul
        assert kg_co2eq > 0.0

    @pytest.mark.asyncio
    async def test_calculate_plane_emissions_factor_not_found(self, mock_session):
        """Test plane emissions when impact factor is not found."""
        origin = Location(
            transport_mode="plane",
            name="Airport A",
            latitude=47.0,
            longitude=8.0,
            iata_code="AAA",
            countrycode="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Airport B",
            latitude=47.5,
            longitude=8.5,
            iata_code="BBB",
            countrycode="CH",
        )

        # Mock query returning None (factor not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.calculate_plane_emissions(
                origin_airport=origin,
                dest_airport=dest,
                class_="eco",
                number_of_trips=1,
            )

        assert exc_info.value.status_code == 500
        assert "Impact factor not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_calculate_plane_emissions_with_rfi_adjustment(
        self, mock_session, sample_airports
    ):
        """Test plane emissions with RFI adjustment factor."""
        origin, dest = sample_airports

        factor = PlaneImpactFactor(
            category="short_haul",
            impact_score=0.25,
            rfi_adjustment=1.5,  # Higher RFI adjustment
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_plane_emissions(
            origin_airport=origin,
            dest_airport=dest,
            class_="eco",
            number_of_trips=1,
        )

        # CO2 should be higher due to RFI adjustment
        assert kg_co2eq > 0.0
        # Should be approximately: distance × 0.25 × 1.5
        expected = distance_km * 0.25 * 1.5
        assert pytest.approx(kg_co2eq, rel=0.01) == expected


class TestCalculateTrainEmissions:
    """Tests for calculate_train_emissions function."""

    @pytest_asyncio.fixture
    async def mock_session(self):
        """Create a mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest_asyncio.fixture
    async def sample_stations(self):
        """Create sample train station locations."""
        origin = Location(
            transport_mode="train",
            name="Zurich Hauptbahnhof",
            latitude=47.3782,
            longitude=8.5402,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Geneva Cornavin",
            latitude=46.2104,
            longitude=6.1427,
            countrycode="CH",
        )
        return origin, dest

    @pytest_asyncio.fixture
    async def mock_ch_factor(self, mock_session):
        """Create a mock Switzerland train impact factor."""
        factor = TrainImpactFactor(
            countrycode="CH",
            impact_score=0.015,
            valid_from=None,
            valid_to=None,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor
        mock_session.execute.return_value = mock_result
        return factor

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_basic(
        self, mock_session, sample_stations, mock_ch_factor
    ):
        """Test basic train emissions calculation."""
        origin, dest = sample_stations
        service = TravelCalculationService(mock_session)

        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Distance should be Haversine * 1.2 (~272km)
        assert distance_km > 200.0
        # CO2 should be: distance × impact_score × trips
        # ~272 × 0.015 × 1 = ~4.08
        assert kg_co2eq > 0.0
        assert pytest.approx(kg_co2eq, rel=0.1) == 4.08

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_multiple_trips(
        self, mock_session, sample_stations, mock_ch_factor
    ):
        """Test train emissions with multiple trips."""
        origin, dest = sample_stations
        service = TravelCalculationService(mock_session)

        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=5,
        )

        # Distance should be the same
        assert distance_km > 200.0
        # CO2 should be 5x (trips multiplier)
        distance_km_single, kg_co2eq_single = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )
        assert pytest.approx(kg_co2eq, rel=0.01) == kg_co2eq_single * 5

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_ch_origin_non_ch_destination(
        self, mock_session
    ):
        """Test train emissions: CH origin to non-CH destination uses non-CH factor."""
        origin = Location(
            transport_mode="train",
            name="Zurich HB",
            latitude=47.3782,
            longitude=8.5402,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            countrycode="FR",
        )

        factor_fr = TrainImpactFactor(
            countrycode="FR",
            impact_score=0.02,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_fr
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Should use FR factor (0.02) - the non-CH country
        assert kg_co2eq > 0.0
        expected = distance_km * 0.02
        assert pytest.approx(kg_co2eq, rel=0.01) == expected

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_non_ch_origin_ch_destination(
        self, mock_session
    ):
        """Test train emissions: non-CH origin to CH destination uses non-CH factor."""
        origin = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            countrycode="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Zurich HB",
            latitude=47.3782,
            longitude=8.5402,
            countrycode="CH",
        )

        factor_fr = TrainImpactFactor(
            countrycode="FR",
            impact_score=0.02,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_fr
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Should use FR factor (0.02) - the non-CH country (origin)
        assert kg_co2eq > 0.0
        expected = distance_km * 0.02
        assert pytest.approx(kg_co2eq, rel=0.01) == expected
        # Verify the query was for "FR", not "CH" or "RoW"
        assert mock_session.execute.call_count == 1
        stmt = mock_session.execute.call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        assert "'FR'" in str(compiled)

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_both_ch_uses_ch_factor(
        self, mock_session, sample_stations
    ):
        """Test train emissions: both CH origin and CH destination uses CH factor."""
        origin, dest = sample_stations  # Both are in CH

        factor_ch = TrainImpactFactor(
            countrycode="CH",
            impact_score=0.00979,  # CH has a much lower factor
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_ch
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Should use CH factor (0.00979)
        assert kg_co2eq > 0.0
        expected = distance_km * 0.00979
        assert pytest.approx(kg_co2eq, rel=0.01) == expected
        # Verify the query was for "CH"
        assert mock_session.execute.call_count == 1
        stmt = mock_session.execute.call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        assert "'CH'" in str(compiled)

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_both_non_ch_uses_destination(
        self, mock_session
    ):
        """Test train emissions: both non-CH uses destination country factor."""
        origin = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            countrycode="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Berlin Hauptbahnhof",
            latitude=52.5251,
            longitude=13.3694,
            countrycode="DE",
        )

        factor_de = TrainImpactFactor(
            countrycode="DE",
            impact_score=0.03,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_de
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Should use DE factor (0.03) - the destination country
        assert kg_co2eq > 0.0
        expected = distance_km * 0.03
        assert pytest.approx(kg_co2eq, rel=0.01) == expected
        # Verify the query was for "DE", not "FR"
        assert mock_session.execute.call_count == 1
        stmt = mock_session.execute.call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        assert "'DE'" in str(compiled)

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_origin_known_dest_none_uses_origin(
        self, mock_session
    ):
        """Test: known origin (FR) + None dest uses origin factor."""
        origin = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            countrycode="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Unknown Station",
            latitude=49.0,
            longitude=3.0,
            countrycode=None,
        )

        factor_fr = TrainImpactFactor(
            countrycode="FR",
            impact_score=0.005,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_fr
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Should use FR factor (0.005) - the known non-CH origin, not RoW
        assert kg_co2eq > 0.0
        expected = distance_km * 0.005
        assert pytest.approx(kg_co2eq, rel=0.01) == expected
        # Verify the query was for "FR", not "RoW"
        assert mock_session.execute.call_count == 1
        stmt = mock_session.execute.call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        assert "'FR'" in str(compiled)

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_origin_none_dest_known_uses_dest(
        self, mock_session
    ):
        """Test: None origin + known dest (FR) uses dest factor."""
        origin = Location(
            transport_mode="train",
            name="Unknown Station",
            latitude=49.0,
            longitude=3.0,
            countrycode=None,
        )
        dest = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            countrycode="FR",
        )

        factor_fr = TrainImpactFactor(
            countrycode="FR",
            impact_score=0.005,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_fr
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Should use FR factor (0.005) - the known non-CH destination, not RoW
        assert kg_co2eq > 0.0
        expected = distance_km * 0.005
        assert pytest.approx(kg_co2eq, rel=0.01) == expected
        # Verify the query was for "FR", not "RoW"
        assert mock_session.execute.call_count == 1
        stmt = mock_session.execute.call_args[0][0]
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        assert "'FR'" in str(compiled)

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_fallback_to_row(self, mock_session):
        """Test that train emissions fallback to RoW if country not found."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            countrycode="XX",  # Non-existent country
        )

        # First query returns None (country not found)
        # Second query returns RoW factor
        mock_result_1 = MagicMock()
        mock_result_1.scalar_one_or_none.return_value = None

        factor_row = TrainImpactFactor(
            countrycode="RoW",
            impact_score=0.025,
        )
        mock_result_2 = MagicMock()
        mock_result_2.scalar_one_or_none.return_value = factor_row

        # Mock execute to return different results on subsequent calls
        mock_session.execute.side_effect = [mock_result_1, mock_result_2]

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        assert kg_co2eq > 0.0
        # Should have called execute twice (once for XX, once for RoW)
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_no_countrycode_uses_row(
        self, mock_session
    ):
        """Test train emissions when destination has no countrycode."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            countrycode=None,  # No countrycode
        )

        factor_row = TrainImpactFactor(
            countrycode="RoW",
            impact_score=0.025,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_row
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        assert kg_co2eq > 0.0
        # Should use RoW factor
        expected = distance_km * 0.025
        assert pytest.approx(kg_co2eq, rel=0.01) == expected

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_factor_not_found(
        self, mock_session, sample_stations
    ):
        """Test train emissions when impact factor is not found."""
        origin, dest = sample_stations

        # Mock query returning None (factor not found, even for RoW)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)

        with pytest.raises(HTTPException) as exc_info:
            await service.calculate_train_emissions(
                origin_station=origin,
                dest_station=dest,
                class_="class_2",
                number_of_trips=1,
            )

        assert exc_info.value.status_code == 500
        assert "Impact factor not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_calculate_train_emissions_different_impact_scores(
        self, mock_session
    ):
        """Test train emissions with different impact scores."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            countrycode="CH",
        )

        # High impact score
        factor_high = TrainImpactFactor(
            countrycode="CH",
            impact_score=0.05,  # Higher impact
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = factor_high
        mock_session.execute.return_value = mock_result

        service = TravelCalculationService(mock_session)
        distance_km, kg_co2eq_high = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # Low impact score
        factor_low = TrainImpactFactor(
            countrycode="CH",
            impact_score=0.01,  # Lower impact
        )
        mock_result.scalar_one_or_none.return_value = factor_low
        mock_session.execute.return_value = mock_result

        distance_km, kg_co2eq_low = await service.calculate_train_emissions(
            origin_station=origin,
            dest_station=dest,
            class_="class_2",
            number_of_trips=1,
        )

        # High impact should produce more CO2
        assert kg_co2eq_high > kg_co2eq_low
        # Ratio should match impact score ratio
        assert pytest.approx(kg_co2eq_high / kg_co2eq_low, rel=0.01) == 5.0
