"""Unit tests for unit totals service.

Tests cover:
- get_unit_totals method with various scenarios
- _calculate_totals_for_year method
- Error handling in module stats retrieval
- Year comparison calculations
- Edge cases (zero FTE, missing previous year data, etc.)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.services.unit_totals_service import UnitTotalsService


# ----------------------
# Fixtures
# ----------------------
@pytest.fixture
def mock_session():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def service(mock_session):
    return UnitTotalsService(mock_session)


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "test-user-123"
    return user


# ----------------------
# get_unit_totals
# ----------------------
@pytest.mark.asyncio
async def test_get_unit_totals_basic(service, mock_user):
    """Test basic unit totals calculation."""
    with patch.object(
        service,
        "_calculate_totals_for_year",
        new=AsyncMock(return_value=(1000.0, 10.0)),
    ) as mock_calc:
        result = await service.get_unit_totals("TEST-UNIT-1", 2023, mock_user)

        assert result["total_kg_co2eq"] == 1000.0
        assert result["total_tonnes_co2eq"] == 1.0
        assert result["total_fte"] == 10.0
        assert result["kg_co2eq_per_fte"] == 100.0
        assert mock_calc.call_count == 2  # Current year and previous year


@pytest.mark.asyncio
async def test_get_unit_totals_zero_fte(service, mock_user):
    """Test unit totals with zero FTE."""
    with patch.object(
        service,
        "_calculate_totals_for_year",
        new=AsyncMock(return_value=(500.0, 0.0)),
    ):
        result = await service.get_unit_totals("TEST-UNIT-1", 2023, mock_user)

        assert result["total_kg_co2eq"] == 500.0
        assert result["total_fte"] is None  # Service returns None when FTE is 0
        assert result["kg_co2eq_per_fte"] is None  # Should be None when FTE is 0


@pytest.mark.asyncio
async def test_get_unit_totals_with_previous_year(service, mock_user):
    """Test unit totals with previous year comparison."""

    def mock_calc_side_effect(unit_id, year, user):
        if year == 2023:
            return (1000.0, 10.0)  # Current year
        elif year == 2022:
            return (800.0, 10.0)  # Previous year
        return (0.0, 0.0)

    with patch.object(
        service,
        "_calculate_totals_for_year",
        new=AsyncMock(side_effect=mock_calc_side_effect),
    ):
        result = await service.get_unit_totals("TEST-UNIT-1", 2023, mock_user)

        assert result["total_kg_co2eq"] == 1000.0
        assert result["previous_year_total_kg_co2eq"] == 800.0
        assert result["previous_year_total_tonnes_co2eq"] == 0.8
        assert result["year_comparison_percentage"] == 25.0  # (1000-800)/800*100


@pytest.mark.asyncio
async def test_get_unit_totals_no_previous_year(service, mock_user):
    """Test unit totals when previous year data is not available."""

    def mock_calc_side_effect(unit_id, year, user):
        if year == 2023:
            return (1000.0, 10.0)
        else:
            raise Exception("No data")

    with patch.object(
        service,
        "_calculate_totals_for_year",
        new=AsyncMock(side_effect=mock_calc_side_effect),
    ):
        result = await service.get_unit_totals("TEST-UNIT-1", 2023, mock_user)

        assert result["total_kg_co2eq"] == 1000.0
        assert result["previous_year_total_kg_co2eq"] is None
        assert result["previous_year_total_tonnes_co2eq"] is None
        assert result["year_comparison_percentage"] is None


@pytest.mark.asyncio
async def test_get_unit_totals_previous_year_zero(service, mock_user):
    """Test unit totals when previous year has zero emissions."""

    def mock_calc_side_effect(unit_id, year, user):
        if year == 2023:
            return (1000.0, 10.0)
        elif year == 2022:
            return (0.0, 10.0)
        return (0.0, 0.0)

    with patch.object(
        service,
        "_calculate_totals_for_year",
        new=AsyncMock(side_effect=mock_calc_side_effect),
    ):
        result = await service.get_unit_totals("TEST-UNIT-1", 2023, mock_user)

        assert result["total_kg_co2eq"] == 1000.0
        assert result["previous_year_total_kg_co2eq"] == 0.0
        # Should not calculate percentage when previous year is 0
        assert result["year_comparison_percentage"] is None


@pytest.mark.asyncio
async def test_get_unit_totals_decrease_from_previous_year(service, mock_user):
    """Test unit totals with decrease from previous year (negative percentage)."""

    def mock_calc_side_effect(unit_id, year, user):
        if year == 2023:
            return (600.0, 10.0)  # Current year (decreased)
        elif year == 2022:
            return (800.0, 10.0)  # Previous year
        return (0.0, 0.0)

    with patch.object(
        service,
        "_calculate_totals_for_year",
        new=AsyncMock(side_effect=mock_calc_side_effect),
    ):
        result = await service.get_unit_totals("TEST-UNIT-1", 2023, mock_user)

        assert result["total_kg_co2eq"] == 600.0
        assert result["previous_year_total_kg_co2eq"] == 800.0
        assert result["year_comparison_percentage"] == -25.0  # (600-800)/800*100


# ----------------------
# _calculate_totals_for_year
# ----------------------
@pytest.mark.asyncio
async def test_calculate_totals_for_year_basic(service, mock_user):
    """Test calculating totals for a year with all modules."""
    with (
        patch(
            "app.services.unit_totals_service.equipment_service.get_module_stats",
            new=AsyncMock(return_value={"total_kg_co2eq": 500.0}),
        ),
        patch(
            "app.services.unit_totals_service.ProfessionalTravelService",
        ) as mock_travel_service_class,
        patch(
            "app.services.unit_totals_service.HeadcountService",
        ) as mock_headcount_service_class,
    ):
        # Setup mock instances
        mock_travel_service = MagicMock()
        mock_travel_service.get_module_stats = AsyncMock(
            return_value={"total_kg_co2eq": 300.0}
        )
        mock_travel_service_class.return_value = mock_travel_service

        mock_headcount_service = MagicMock()
        mock_headcount_service.get_module_stats = AsyncMock(
            return_value={"submodule1": 5.0, "submodule2": 3.0}
        )
        mock_headcount_service_class.return_value = mock_headcount_service

        total_co2, total_fte = await service._calculate_totals_for_year(
            "TEST-UNIT-1", 2023, mock_user
        )

        assert total_co2 == 800.0  # 500 + 300
        assert total_fte == 8.0  # 5 + 3


@pytest.mark.asyncio
async def test_calculate_totals_for_year_equipment_error(service, mock_user):
    """Test that equipment errors are caught and handled."""
    with (
        patch(
            "app.services.unit_totals_service.equipment_service.get_module_stats",
            new=AsyncMock(side_effect=Exception("Equipment error")),
        ),
        patch(
            "app.services.unit_totals_service.ProfessionalTravelService",
        ) as mock_travel_service_class,
        patch(
            "app.services.unit_totals_service.HeadcountService",
        ) as mock_headcount_service_class,
    ):
        # Setup mock instances
        mock_travel_service = MagicMock()
        mock_travel_service.get_module_stats = AsyncMock(
            return_value={"total_kg_co2eq": 300.0}
        )
        mock_travel_service_class.return_value = mock_travel_service

        mock_headcount_service = MagicMock()
        mock_headcount_service.get_module_stats = AsyncMock(
            return_value={"submodule1": 5.0}
        )
        mock_headcount_service_class.return_value = mock_headcount_service

        total_co2, total_fte = await service._calculate_totals_for_year(
            "TEST-UNIT-1", 2023, mock_user
        )

        # Should continue despite equipment error
        assert total_co2 == 300.0  # Only travel
        assert total_fte == 5.0


@pytest.mark.asyncio
async def test_calculate_totals_for_year_travel_error(service, mock_user):
    """Test that travel errors are caught and handled."""
    with (
        patch(
            "app.services.unit_totals_service.equipment_service.get_module_stats",
            new=AsyncMock(return_value={"total_kg_co2eq": 500.0}),
        ),
        patch(
            "app.services.unit_totals_service.ProfessionalTravelService",
        ) as mock_travel_service_class,
        patch(
            "app.services.unit_totals_service.HeadcountService",
        ) as mock_headcount_service_class,
    ):
        # Setup mock instances
        mock_travel_service = MagicMock()
        mock_travel_service.get_module_stats = AsyncMock(
            side_effect=Exception("Travel error")
        )
        mock_travel_service_class.return_value = mock_travel_service

        mock_headcount_service = MagicMock()
        mock_headcount_service.get_module_stats = AsyncMock(
            return_value={"submodule1": 5.0}
        )
        mock_headcount_service_class.return_value = mock_headcount_service

        total_co2, total_fte = await service._calculate_totals_for_year(
            "TEST-UNIT-1", 2023, mock_user
        )

        # Should continue despite travel error
        assert total_co2 == 500.0  # Only equipment
        assert total_fte == 5.0


@pytest.mark.asyncio
async def test_calculate_totals_for_year_headcount_error(service, mock_user):
    """Test that headcount errors are caught and return 0 FTE."""
    with (
        patch(
            "app.services.unit_totals_service.equipment_service.get_module_stats",
            new=AsyncMock(return_value={"total_kg_co2eq": 500.0}),
        ),
        patch(
            "app.services.unit_totals_service.ProfessionalTravelService",
        ) as mock_travel_service_class,
        patch(
            "app.services.unit_totals_service.HeadcountService",
        ) as mock_headcount_service_class,
    ):
        # Setup mock instances
        mock_travel_service = MagicMock()
        mock_travel_service.get_module_stats = AsyncMock(
            return_value={"total_kg_co2eq": 300.0}
        )
        mock_travel_service_class.return_value = mock_travel_service

        mock_headcount_service = MagicMock()
        mock_headcount_service.get_module_stats = AsyncMock(
            side_effect=Exception("Headcount error")
        )
        mock_headcount_service_class.return_value = mock_headcount_service

        total_co2, total_fte = await service._calculate_totals_for_year(
            "TEST-UNIT-1", 2023, mock_user
        )

        assert total_co2 == 800.0  # Equipment + travel
        assert total_fte == 0.0  # Should default to 0 on error


@pytest.mark.asyncio
async def test_calculate_totals_for_year_missing_co2_values(service, mock_user):
    """Test handling of missing or None CO2 values."""
    with (
        patch(
            "app.services.unit_totals_service.equipment_service.get_module_stats",
            new=AsyncMock(return_value={}),  # Missing total_kg_co2eq
        ),
        patch(
            "app.services.unit_totals_service.ProfessionalTravelService",
        ) as mock_travel_service_class,
        patch(
            "app.services.unit_totals_service.HeadcountService",
        ) as mock_headcount_service_class,
    ):
        # Setup mock instances
        mock_travel_service = MagicMock()
        mock_travel_service.get_module_stats = AsyncMock(
            return_value={"total_kg_co2eq": None}
        )
        mock_travel_service_class.return_value = mock_travel_service

        mock_headcount_service = MagicMock()
        mock_headcount_service.get_module_stats = AsyncMock(
            return_value={"submodule1": 5.0}
        )
        mock_headcount_service_class.return_value = mock_headcount_service

        total_co2, total_fte = await service._calculate_totals_for_year(
            "TEST-UNIT-1", 2023, mock_user
        )

        assert total_co2 == 0.0  # Should handle None/missing gracefully
        assert total_fte == 5.0


@pytest.mark.asyncio
async def test_calculate_totals_for_year_headcount_non_numeric_values(
    service, mock_user
):
    """Test that non-numeric headcount values are filtered out."""
    with (
        patch(
            "app.services.unit_totals_service.equipment_service.get_module_stats",
            new=AsyncMock(return_value={"total_kg_co2eq": 500.0}),
        ),
        patch(
            "app.services.unit_totals_service.ProfessionalTravelService",
        ) as mock_travel_service_class,
        patch(
            "app.services.unit_totals_service.HeadcountService",
        ) as mock_headcount_service_class,
    ):
        # Setup mock instances
        mock_travel_service = MagicMock()
        mock_travel_service.get_module_stats = AsyncMock(
            return_value={"total_kg_co2eq": 300.0}
        )
        mock_travel_service_class.return_value = mock_travel_service

        mock_headcount_service = MagicMock()
        mock_headcount_service.get_module_stats = AsyncMock(
            return_value={
                "submodule1": 5.0,
                "submodule2": 3.0,
                "submodule3": "invalid",  # Non-numeric
                "submodule4": None,  # None value
            }
        )
        mock_headcount_service_class.return_value = mock_headcount_service

        total_co2, total_fte = await service._calculate_totals_for_year(
            "TEST-UNIT-1", 2023, mock_user
        )

        assert total_co2 == 800.0
        assert total_fte == 8.0  # Only 5.0 + 3.0, ignoring invalid values
