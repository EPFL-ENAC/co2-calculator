from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.services import equipment_service

# --- Mocks for Repositories and Logic ---


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_equipment_repo():
    with patch("app.services.equipment_service.equipment_repo", autospec=True) as repo:
        repo.get_equipment_summary_by_submodule = AsyncMock()
        repo.get_equipment_with_emissions = AsyncMock()
        repo.get_by_id = AsyncMock()
        repo.create_equipment = AsyncMock()
        repo.update_equipment = AsyncMock()
        repo.insert_emission = AsyncMock()
        repo.retire_current_emission = AsyncMock()
        repo.get_current_emission_factor = AsyncMock()
        yield repo


@pytest.fixture
def mock_pf_repo():
    with patch(
        "app.services.equipment_service.PowerFactorRepository",
        autospec=True,
    ) as repo_class:
        instance = repo_class.return_value
        instance.get_power_factor = AsyncMock()
        yield instance


@pytest.fixture
def mock_calc_service():
    with patch(
        "app.services.equipment_service.calculate_equipment_emission_versioned",
        new_callable=AsyncMock,
    ) as calc:
        yield calc


# --- Tests for get_module_data ---


@pytest.mark.asyncio
async def test_get_module_data_preview_limit_none(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_equipment_summary_by_submodule = AsyncMock(
        return_value={
            "scientific": {
                "total_items": 5,
                "annual_consumption_kwh": 100.0,
                "total_kg_co2eq": 20.0,
            }
        }
    )

    mock_equipment_repo.get_equipment_with_emissions.return_value = ([], 5)

    # Execute
    response = await equipment_service.get_module_data(
        mock_session, "unit123", 2024, preview_limit=None
    )

    # Assert
    assert response.submodules["scientific"].items == []
    assert response.submodules["scientific"].count == 5
    # Verify summary logic
    assert response.totals.total_items == 5


@pytest.mark.asyncio
async def test_get_module_data_empty_summary(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_equipment_summary_by_submodule.return_value = {}

    mock_equipment_repo.get_equipment_with_emissions.return_value = ([], 5)
    # Execute
    response = await equipment_service.get_module_data(
        mock_session, "unit123", 2024, preview_limit=5
    )

    # Assert
    assert "scientific" in response.submodules
    assert len(response.submodules["scientific"].items) == 0
    assert response.submodules["scientific"].count == 5
    # Verify summary logic
    assert response.totals.total_items == 0


@pytest.mark.asyncio
async def test_get_module_data_nonexistent_submodule(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_equipment_summary_by_submodule.return_value = {
        "scientific": {
            "total_items": 5,
            "annual_consumption_kwh": 100.0,
            "total_kg_co2eq": 20.0,
        }
    }
    mock_equipment_repo.get_equipment_with_emissions.return_value = ([], 5)

    # Execute
    response = await equipment_service.get_module_data(
        mock_session, "unit123", 2024, preview_limit=5
    )

    # Assert
    assert "scientific" in response.submodules
    assert "it" in response.submodules
    assert "other" in response.submodules
    assert len(response.submodules["it"].items) == 0
    assert len(response.submodules["other"].items) == 0


# --- Tests for get_submodule_data ---


@pytest.mark.asyncio
async def test_get_submodule_data_sorting(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_equipment_with_emissions.return_value = ([], 10)
    mock_equipment_repo.get_equipment_summary_by_submodule.return_value = {}

    # Execute
    response = await equipment_service.get_submodule_data(
        mock_session, "unit1", "it", limit=5, offset=0, sort_by="name", sort_order="asc"
    )

    # Assert
    assert response.has_more is True


@pytest.mark.asyncio
async def test_get_submodule_data_limit_zero(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_equipment_with_emissions.return_value = ([], 10)
    mock_equipment_repo.get_equipment_summary_by_submodule.return_value = {}

    # Execute
    response = await equipment_service.get_submodule_data(
        mock_session, "unit1", "it", limit=0, offset=0
    )

    # Assert
    assert response.has_more is True
    assert len(response.items) == 0


@pytest.mark.asyncio
async def test_get_submodule_data_offset_zero(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_equipment_with_emissions.return_value = ([], 10)
    mock_equipment_repo.get_equipment_summary_by_submodule.return_value = {}

    # Execute
    response = await equipment_service.get_submodule_data(
        mock_session, "unit1", "it", limit=100, offset=0
    )

    # Assert
    assert response.has_more is True


@pytest.mark.asyncio
async def test_get_submodule_data_offset_nonzero(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_equipment_with_emissions.return_value = ([], 10)
    mock_equipment_repo.get_equipment_summary_by_submodule.return_value = {}

    # Execute
    response = await equipment_service.get_submodule_data(
        mock_session, "unit1", "it", limit=100, offset=100
    )

    # Assert
    assert response.has_more is False


@pytest.mark.asyncio
async def test_delete_equipment_not_found(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_by_id.return_value = None

    # Execute
    with pytest.raises(HTTPException) as exc:
        await equipment_service.delete_equipment(mock_session, 999, "user1")
    assert exc.value.status_code == 404
