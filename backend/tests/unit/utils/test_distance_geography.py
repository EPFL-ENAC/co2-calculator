"""Unit tests for distance and geography utilities.

Tests cover:
- Distance calculation functions (haversine_distance,
  calculate_plane_distance, calculate_train_distance)
- Haul category determination (get_haul_category)
- Train country code selection logic (issue #357)
- Flight factor resolution (resolve_flight_factor)
- Train factor resolution (resolve_train_factor)
"""

import pytest

from app.models.factor import Factor
from app.models.location import Location
from app.utils.distance_geography import (
    _determine_train_countrycode,
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
    haversine_distance,
    resolve_flight_factor,
    resolve_train_factor,
)

# ---- Tests from former test_travel_calculation_service.py ---- #
# Adapted to test the current pure functions in distance_geography.py
# after TravelCalculationService was removed (logic moved to
# data_entry_emission_service.py + distance_geography.py).


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
                lon1=8.5402,
                lat2=47.3782,
                lon2=8.5402,
            )

    def test_haversine_invalid_longitude(self):
        """Test Haversine distance with invalid longitude."""
        with pytest.raises(ValueError, match="Invalid longitude"):
            haversine_distance(
                lat1=47.3782,
                lon1=181.0,
                lat2=47.3782,
                lon2=8.5402,
            )

    def test_haversine_boundary_latitude_90(self):
        """Test Haversine distance with boundary latitude values."""
        # North pole to equator
        result = haversine_distance(lat1=90.0, lon1=0.0, lat2=0.0, lon2=0.0)
        assert pytest.approx(result, rel=0.1) == 10000.0

    def test_haversine_boundary_latitude_negative_90(self):
        """Test Haversine distance with negative boundary latitude."""
        # South pole to equator
        result = haversine_distance(lat1=-90.0, lon1=0.0, lat2=0.0, lon2=0.0)
        assert pytest.approx(result, rel=0.1) == 10000.0

    def test_haversine_boundary_longitude_180(self):
        """Test Haversine distance with boundary longitude values."""
        # 180 degrees longitude (International Date Line)
        result = haversine_distance(lat1=0.0, lon1=180.0, lat2=0.0, lon2=-180.0)
        assert result == 0

    def test_haversine_invalid_latitude_too_low(self):
        """Test Haversine distance with latitude < -90."""
        with pytest.raises(ValueError, match="Invalid latitude"):
            haversine_distance(lat1=-91.0, lon1=0.0, lat2=0.0, lon2=0.0)

    def test_haversine_invalid_longitude_too_low(self):
        """Test Haversine distance with longitude < -180."""
        with pytest.raises(ValueError, match="Invalid longitude"):
            haversine_distance(lat1=0.0, lon1=-181.0, lat2=0.0, lon2=0.0)

    def test_haversine_both_coordinates_invalid(self):
        """Test Haversine distance with both coordinates invalid."""
        with pytest.raises(ValueError, match="Invalid latitude"):
            haversine_distance(lat1=91.0, lon1=181.0, lat2=0.0, lon2=0.0)

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
            country_code="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Geneva Airport",
            latitude=46.2380,
            longitude=6.1090,
            iata_code="GVA",
            country_code="CH",
        )

        result = calculate_plane_distance(origin, dest)

        # Haversine distance Zurich-Geneva is ~227km, so result should be ~322km
        assert result > 227.0
        assert pytest.approx(result, rel=0.1) == 322.0  # 227 + 95

    def test_plane_distance_same_location(self):
        """Test plane distance for same location."""
        origin = Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            country_code="CH",
        )

        result = calculate_plane_distance(origin, origin)

        # Should be 0 + 95 = 95 km
        assert result == 95.0

    def test_plane_distance_short(self):
        """Test plane distance for very short flight."""
        origin = Location(
            transport_mode="plane",
            name="Airport 1",
            latitude=47.0,
            longitude=8.0,
            iata_code="A1",
            country_code="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Airport 2",
            latitude=47.1,
            longitude=8.1,
            iata_code="A2",
            country_code="CH",
        )

        result = calculate_plane_distance(origin, dest)
        assert result >= 95


class TestCalculateTrainDistance:
    """Tests for calculate_train_distance function."""

    def test_train_distance_basic(self):
        """Test basic train distance calculation (Haversine * 1.2)."""
        origin = Location(
            transport_mode="train",
            name="Zurich Hauptbahnhof",
            latitude=47.3782,
            longitude=8.5402,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Geneva Cornavin",
            latitude=46.2104,
            longitude=6.1427,
            country_code="CH",
        )

        result = calculate_train_distance(origin, dest)

        # Haversine distance Zurich-Geneva is ~227km, so result should be ~272km
        assert result > 227.0
        assert pytest.approx(result, rel=0.1) == 272.0  # 227 * 1.2

    def test_train_distance_same_location(self):
        """Test train distance for same location."""
        origin = Location(
            transport_mode="train",
            name="Zurich Hauptbahnhof",
            latitude=47.3782,
            longitude=8.5402,
            country_code="CH",
        )

        result = calculate_train_distance(origin, origin)
        assert result == 0.0

    def test_train_distance_multiplier(self):
        """Test that train distance uses 1.2 multiplier correctly."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code="CH",
        )

        haversine_dist = haversine_distance(
            origin.latitude, origin.longitude, dest.latitude, dest.longitude
        )
        train_dist = calculate_train_distance(origin, dest)

        assert pytest.approx(train_dist, rel=0.01) == haversine_dist * 1.2

    def test_train_distance_rounding(self):
        """Test train distance rounding."""
        origin = Location(
            transport_mode="train",
            name="Station 1",
            latitude=47.0,
            longitude=8.0,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station 2",
            latitude=47.1,
            longitude=8.1,
            country_code="CH",
        )

        result = calculate_train_distance(origin, dest)
        assert isinstance(result, int)


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
            (0.0, "very_short_haul"),
            (100, "very_short_haul"),
            (400.0, "very_short_haul"),
            (500, "very_short_haul"),
            (799.9, "very_short_haul"),
            (800, "short_haul"),
            (800.0, "short_haul"),
            (1200, "short_haul"),
            (1200.0, "short_haul"),
            (1499.9, "short_haul"),
            (1500, "medium_haul"),
            (1500.0, "medium_haul"),
            (3000, "medium_haul"),
            (3000.0, "medium_haul"),
            (3999.9, "medium_haul"),
            (4000, "long_haul"),
            (4000.0, "long_haul"),
            (8000, "long_haul"),
            (8000.0, "long_haul"),
        ],
    )
    def test_haul_category_parametrized(self, distance, category):
        """Test haul category at boundary values."""
        assert get_haul_category(distance) == category


# ---- Tests for _determine_train_countrycode (issue #357) ---- #
# Ported from TestCalculateTrainEmissions in the former
# test_travel_calculation_service.py — these tested the country
# selection logic that lived inside TravelCalculationService and
# is now extracted into _determine_train_countrycode.


class TestDetermineTrainCountrycode:
    """Tests for the train country code selection logic from issue #357."""

    def test_both_ch_returns_ch(self):
        """When both origin and destination are in CH, use CH factor."""
        origin = Location(
            transport_mode="train",
            name="Zürich HB",
            latitude=47.3782,
            longitude=8.5402,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Genève",
            latitude=46.2104,
            longitude=6.1427,
            country_code="CH",
        )
        assert _determine_train_countrycode(origin, dest) == "CH"

    def test_ch_to_foreign_returns_destination(self):
        """CH origin to foreign destination: use destination country (DE)."""
        origin = Location(
            transport_mode="train",
            name="Basel SBB",
            latitude=47.5476,
            longitude=7.5898,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Freiburg Hbf",
            latitude=47.9977,
            longitude=7.8421,
            country_code="DE",
        )
        assert _determine_train_countrycode(origin, dest) == "DE"

    def test_foreign_to_ch_returns_origin(self):
        """Foreign origin to CH destination: use origin (non-CH) country (FR)."""
        origin = Location(
            transport_mode="train",
            name="Lyon Part-Dieu",
            latitude=45.7606,
            longitude=4.8590,
            country_code="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Genève",
            latitude=46.2104,
            longitude=6.1427,
            country_code="CH",
        )
        assert _determine_train_countrycode(origin, dest) == "FR"

    def test_both_foreign_returns_destination(self):
        """Both foreign (FR -> DE): prefer destination country."""
        origin = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            country_code="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Berlin Hauptbahnhof",
            latitude=52.5251,
            longitude=13.3694,
            country_code="DE",
        )
        assert _determine_train_countrycode(origin, dest) == "DE"

    def test_origin_known_dest_none_uses_origin(self):
        """Known origin (FR) + None dest: use origin factor."""
        origin = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            country_code="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Unknown Station",
            latitude=49.0,
            longitude=3.0,
            country_code=None,
        )
        assert _determine_train_countrycode(origin, dest) == "FR"

    def test_origin_none_dest_known_uses_dest(self):
        """None origin + known dest (FR): use dest factor."""
        origin = Location(
            transport_mode="train",
            name="Unknown Station",
            latitude=49.0,
            longitude=3.0,
            country_code=None,
        )
        dest = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            country_code="FR",
        )
        assert _determine_train_countrycode(origin, dest) == "FR"

    def test_ch_origin_none_dest_falls_back_to_row(self):
        """CH origin + None destination: fall back to RoW."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code=None,
        )
        assert _determine_train_countrycode(origin, dest) == "RoW"

    def test_none_origin_ch_dest_falls_back_to_row(self):
        """None origin + CH destination: fall back to RoW."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code=None,
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code="CH",
        )
        assert _determine_train_countrycode(origin, dest) == "RoW"

    def test_both_none_returns_row(self):
        """Both have no country code: fall back to RoW."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code=None,
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code=None,
        )
        assert _determine_train_countrycode(origin, dest) == "RoW"


# ---- Tests for resolve_flight_factor ---- #
# Ported from TestCalculatePlaneEmissions in the former
# test_travel_calculation_service.py — adapted from mock-based
# service tests to direct pure-function tests.


def _make_plane_factor(category: str, impact_score: float, rfi_adjustment: float):
    """Helper to create a plane Factor."""
    return Factor(
        id=None,
        emission_type_id=7,
        data_entry_type_id=20,
        classification={"kind": "plane", "category": category},
        values={
            "impact_score": impact_score,
            "rfi_adjustment": rfi_adjustment,
        },
    )


def _make_train_factor(country_code: str, impact_score: float):
    """Helper to create a train Factor."""
    return Factor(
        id=None,
        emission_type_id=7,
        data_entry_type_id=20,
        classification={"kind": "train", "country_code": country_code},
        values={"impact_score": impact_score},
    )


class TestResolveFlightFactor:
    """Tests for resolve_flight_factor: distance + haul category matching."""

    @pytest.fixture
    def plane_factors(self) -> list[Factor]:
        """Plane factors covering all haul categories (from seed data)."""
        return [
            _make_plane_factor("very_short_haul", 0.174, 2.7),
            _make_plane_factor("short_haul", 0.134, 2.7),
            _make_plane_factor("medium_haul", 0.11, 2.7),
            _make_plane_factor("long_haul", 0.108, 2.7),
        ]

    def test_very_short_haul_zurich_geneva(self, plane_factors):
        """ZRH -> GVA (~322 km) should match very_short_haul."""
        origin = Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            country_code="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Geneva Airport",
            latitude=46.2380,
            longitude=6.1090,
            iata_code="GVA",
            country_code="CH",
        )
        distance_km, factor = resolve_flight_factor(origin, dest, plane_factors)

        assert distance_km > 0
        assert distance_km < 800
        assert factor is not None
        assert factor.classification["category"] == "very_short_haul"
        assert factor.values["impact_score"] == 0.174

    def test_long_haul_zurich_new_york(self, plane_factors):
        """ZRH -> JFK (~6300 km) should match long_haul."""
        origin = Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            country_code="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="JFK Airport",
            latitude=40.6413,
            longitude=-73.7781,
            iata_code="JFK",
            country_code="US",
        )
        distance_km, factor = resolve_flight_factor(origin, dest, plane_factors)

        assert distance_km > 4000
        assert factor is not None
        assert factor.classification["category"] == "long_haul"
        assert factor.values["impact_score"] == 0.108

    def test_distance_includes_approach_km(self, plane_factors):
        """Distance should include the +95 km approach adjustment."""
        origin = Location(
            transport_mode="plane",
            name="Zurich Airport",
            latitude=47.4647,
            longitude=8.5492,
            iata_code="ZRH",
            country_code="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Geneva Airport",
            latitude=46.2380,
            longitude=6.1090,
            iata_code="GVA",
            country_code="CH",
        )
        distance_km, _ = resolve_flight_factor(origin, dest, plane_factors)

        raw_haversine = haversine_distance(47.4647, 8.5492, 46.2380, 6.1090)
        assert distance_km == round(raw_haversine + 95)

    def test_no_matching_factor_returns_none(self):
        """If no factor matches the haul category, return None."""
        origin = Location(
            transport_mode="plane",
            name="Airport A",
            latitude=47.4647,
            longitude=8.5492,
            country_code="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Airport B",
            latitude=46.2380,
            longitude=6.1090,
            country_code="CH",
        )
        # Only long_haul factor, but distance is very short
        factors = [_make_plane_factor("long_haul", 0.108, 2.7)]
        distance_km, factor = resolve_flight_factor(origin, dest, factors)

        assert distance_km > 0
        assert factor is None

    def test_empty_factors_returns_none(self):
        """Empty factor list should return None."""
        origin = Location(
            transport_mode="plane",
            name="Airport A",
            latitude=47.4647,
            longitude=8.5492,
            country_code="CH",
        )
        dest = Location(
            transport_mode="plane",
            name="Airport B",
            latitude=46.2380,
            longitude=6.1090,
            country_code="CH",
        )
        distance_km, factor = resolve_flight_factor(origin, dest, [])

        assert distance_km > 0
        assert factor is None


# ---- Tests for resolve_train_factor ---- #
# Ported from TestCalculateTrainEmissions in the former
# test_travel_calculation_service.py — adapted from mock-based
# service tests to direct pure-function tests.


class TestResolveTrainFactor:
    """Tests for resolve_train_factor: distance + country code matching."""

    @pytest.fixture
    def train_factors(self) -> list[Factor]:
        """Train factors from seed data."""
        return [
            _make_train_factor("CH", 0.00979),
            _make_train_factor("FR", 0.0269),
            _make_train_factor("DE", 0.0719),
            _make_train_factor("IT", 0.0491),
            _make_train_factor("AT", 0.0608),
            _make_train_factor("RoW", 0.0775),
        ]

    def test_ch_to_ch_uses_ch_factor(self, train_factors):
        """Both stations in CH: use CH factor."""
        origin = Location(
            transport_mode="train",
            name="Zürich HB",
            latitude=47.3782,
            longitude=8.5402,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Genève",
            latitude=46.2104,
            longitude=6.1427,
            country_code="CH",
        )
        distance_km, factor = resolve_train_factor(origin, dest, train_factors)

        assert distance_km > 0
        assert factor is not None
        assert factor.classification["country_code"] == "CH"
        assert factor.values["impact_score"] == 0.00979

    def test_ch_to_de_uses_de_factor(self, train_factors):
        """CH to DE: use DE factor (non-CH destination)."""
        origin = Location(
            transport_mode="train",
            name="Basel SBB",
            latitude=47.5476,
            longitude=7.5898,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Freiburg Hbf",
            latitude=47.9977,
            longitude=7.8421,
            country_code="DE",
        )
        distance_km, factor = resolve_train_factor(origin, dest, train_factors)

        assert distance_km > 0
        assert factor is not None
        assert factor.classification["country_code"] == "DE"

    def test_fr_to_de_uses_de_factor(self, train_factors):
        """FR to DE: prefer destination country."""
        origin = Location(
            transport_mode="train",
            name="Paris Gare du Nord",
            latitude=48.8809,
            longitude=2.3553,
            country_code="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Berlin Hauptbahnhof",
            latitude=52.5251,
            longitude=13.3694,
            country_code="DE",
        )
        distance_km, factor = resolve_train_factor(origin, dest, train_factors)

        assert distance_km > 0
        assert factor is not None
        assert factor.classification["country_code"] == "DE"

    def test_fr_to_ch_uses_fr_factor(self, train_factors):
        """FR to CH: use FR factor (non-CH origin preferred over CH dest)."""
        origin = Location(
            transport_mode="train",
            name="Lyon Part-Dieu",
            latitude=45.7606,
            longitude=4.8590,
            country_code="FR",
        )
        dest = Location(
            transport_mode="train",
            name="Genève",
            latitude=46.2104,
            longitude=6.1427,
            country_code="CH",
        )
        distance_km, factor = resolve_train_factor(origin, dest, train_factors)

        assert distance_km > 0
        assert factor is not None
        assert factor.classification["country_code"] == "FR"

    def test_unknown_country_falls_back_to_row(self, train_factors):
        """Unknown country code (XX) falls back to RoW."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code="XX",
        )
        distance_km, factor = resolve_train_factor(origin, dest, train_factors)

        assert distance_km > 0
        assert factor is not None
        assert factor.classification["country_code"] == "RoW"

    def test_no_country_code_uses_row(self, train_factors):
        """Destination with no country_code + CH origin: use RoW."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code=None,
        )
        distance_km, factor = resolve_train_factor(origin, dest, train_factors)

        assert distance_km > 0
        assert factor is not None
        assert factor.classification["country_code"] == "RoW"

    def test_distance_includes_routing_factor(self, train_factors):
        """Distance should include the x1.2 routing factor."""
        origin = Location(
            transport_mode="train",
            name="Zürich HB",
            latitude=47.3782,
            longitude=8.5402,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Genève",
            latitude=46.2104,
            longitude=6.1427,
            country_code="CH",
        )
        distance_km, _ = resolve_train_factor(origin, dest, train_factors)

        raw_haversine = haversine_distance(47.3782, 8.5402, 46.2104, 6.1427)
        assert distance_km == round(raw_haversine * 1.2)

    def test_empty_factors_returns_none(self):
        """Empty factor list should return None."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code="CH",
        )
        dest = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code="CH",
        )
        distance_km, factor = resolve_train_factor(origin, dest, [])

        assert distance_km > 0
        assert factor is None

    def test_higher_impact_score_produces_selection(self, train_factors):
        """Verify correct factor is selected based on country, not impact score."""
        origin = Location(
            transport_mode="train",
            name="Station A",
            latitude=47.0,
            longitude=8.0,
            country_code="CH",
        )
        dest_ch = Location(
            transport_mode="train",
            name="Station B",
            latitude=48.0,
            longitude=9.0,
            country_code="CH",
        )
        dest_de = Location(
            transport_mode="train",
            name="Station C",
            latitude=48.0,
            longitude=9.0,
            country_code="DE",
        )

        _, factor_ch = resolve_train_factor(origin, dest_ch, train_factors)
        _, factor_de = resolve_train_factor(origin, dest_de, train_factors)

        assert factor_ch is not None
        assert factor_de is not None
        # DE has higher impact than CH
        assert factor_de.values["impact_score"] > factor_ch.values["impact_score"]
