"""Unit tests for distance and geography utilities.

Tests cover edge cases and boundary conditions for distance calculations.
"""

import pytest

from app.models.location import Location
from app.utils.distance_geography import (
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
    haversine_distance,
)


class TestHaversineDistanceEdgeCases:
    """Tests for haversine_distance edge cases."""

    def test_haversine_boundary_latitude_90(self):
        """Test Haversine distance with boundary latitude values."""
        # North pole to equator
        result = haversine_distance(
            lat1=90.0,
            lon1=0.0,
            lat2=0.0,
            lon2=0.0,
        )
        # Should be approximately 10000 km (quarter of Earth's circumference)
        assert pytest.approx(result, rel=0.1) == 10000.0

    def test_haversine_boundary_latitude_negative_90(self):
        """Test Haversine distance with negative boundary latitude."""
        # South pole to equator
        result = haversine_distance(
            lat1=-90.0,
            lon1=0.0,
            lat2=0.0,
            lon2=0.0,
        )
        assert pytest.approx(result, rel=0.1) == 10000.0

    def test_haversine_boundary_longitude_180(self):
        """Test Haversine distance with boundary longitude values."""
        # 180 degrees longitude (International Date Line)
        result = haversine_distance(
            lat1=0.0,
            lon1=180.0,
            lat2=0.0,
            lon2=-180.0,
        )
        # Should be 0 (same point, different representation)
        assert result == 0

    def test_haversine_invalid_latitude_too_high(self):
        """Test Haversine distance with latitude > 90."""
        with pytest.raises(ValueError, match="Invalid latitude"):
            haversine_distance(
                lat1=91.0,
                lon1=0.0,
                lat2=0.0,
                lon2=0.0,
            )

    def test_haversine_invalid_latitude_too_low(self):
        """Test Haversine distance with latitude < -90."""
        with pytest.raises(ValueError, match="Invalid latitude"):
            haversine_distance(
                lat1=-91.0,
                lon1=0.0,
                lat2=0.0,
                lon2=0.0,
            )

    def test_haversine_invalid_longitude_too_high(self):
        """Test Haversine distance with longitude > 180."""
        with pytest.raises(ValueError, match="Invalid longitude"):
            haversine_distance(
                lat1=0.0,
                lon1=181.0,
                lat2=0.0,
                lon2=0.0,
            )

    def test_haversine_invalid_longitude_too_low(self):
        """Test Haversine distance with longitude < -180."""
        with pytest.raises(ValueError, match="Invalid longitude"):
            haversine_distance(
                lat1=0.0,
                lon1=-181.0,
                lat2=0.0,
                lon2=0.0,
            )

    def test_haversine_both_coordinates_invalid(self):
        """Test Haversine distance with both coordinates invalid."""
        with pytest.raises(ValueError, match="Invalid latitude"):
            haversine_distance(
                lat1=91.0,
                lon1=181.0,
                lat2=0.0,
                lon2=0.0,
            )


class TestGetHaulCategory:
    """Tests for get_haul_category function."""

    def test_very_short_haul(self):
        """Test very short haul category (< 800 km)."""
        assert get_haul_category(100.0) == "very_short_haul"
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
        assert get_haul_category(2000.0) == "medium_haul"
        assert get_haul_category(3999.9) == "medium_haul"

    def test_long_haul(self):
        """Test long haul category (> 4000 km)."""
        assert get_haul_category(4000.0) == "long_haul"
        assert get_haul_category(5000.0) == "long_haul"
        assert get_haul_category(10000.0) == "long_haul"

    @pytest.mark.parametrize(
        "distance,expected",
        [
            (0.0, "very_short_haul"),
            (400.0, "very_short_haul"),
            (799.9, "very_short_haul"),
            (800.0, "short_haul"),
            (1200.0, "short_haul"),
            (1499.9, "short_haul"),
            (1500.0, "medium_haul"),
            (3000.0, "medium_haul"),
            (3999.9, "medium_haul"),
            (4000.0, "long_haul"),
            (8000.0, "long_haul"),
        ],
    )
    def test_haul_category_boundaries(self, distance, expected):
        """Test haul category at boundary values."""
        assert get_haul_category(distance) == expected


class TestCalculatePlaneDistance:
    """Tests for calculate_plane_distance function."""

    def test_plane_distance_basic(self):
        """Test basic plane distance calculation."""
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
        # Should be haversine distance + 95 km
        haversine_dist = haversine_distance(
            origin.latitude, origin.longitude, dest.latitude, dest.longitude
        )
        expected = round(haversine_dist + 95.0)
        assert result == expected

    def test_plane_distance_short(self):
        """Test plane distance for very short flight."""
        origin = Location(
            transport_mode="plane",
            name="Airport 1",
            latitude=47.0,
            longitude=8.0,
            iata_code="A1",
            countrycode="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Airport 2",
            latitude=47.1,
            longitude=8.1,
            iata_code="A2",
            countrycode="CH",
        )

        result = calculate_plane_distance(origin, dest)
        # Even short distances should have the 95 km addition
        assert result >= 95


class TestCalculateTrainDistance:
    """Tests for calculate_train_distance function."""

    def test_train_distance_basic(self):
        """Test basic train distance calculation."""
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
        # Should be haversine distance * 1.2
        haversine_dist = haversine_distance(
            origin.latitude, origin.longitude, dest.latitude, dest.longitude
        )
        expected = round(haversine_dist * 1.2)
        assert result == expected

    def test_train_distance_rounding(self):
        """Test train distance rounding."""
        origin = Location(
            transport_mode="train",
            name="Station 1",
            latitude=47.0,
            longitude=8.0,
            countrycode="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station 2",
            latitude=47.1,
            longitude=8.1,
            countrycode="CH",
        )

        result = calculate_train_distance(origin, dest)
        # Result should be an integer
        assert isinstance(result, int)
