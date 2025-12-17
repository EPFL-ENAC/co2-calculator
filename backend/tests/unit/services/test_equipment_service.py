from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.schemas.equipment import (
    EquipmentUpdateRequest,
)
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


# --- Tests for create_equipment ---


# @pytest.mark.asyncio
# async def test_create_equipment_empty_name(
#     mock_session, mock_equipment_repo, mock_pf_repo, mock_calc_service
# ):
#     # Setup input
#     data = EquipmentCreateRequest(
#         unit_id="unit1", name="", submodule="scientific", class_="ClassA"
#     )

#     # Setup Repo Mocks
#     mock_pf = MagicMock(id=10, active_power_w=100, standby_power_w=10)
#     mock_pf_repo.get_power_factor.return_value = mock_pf

#     mock_created_eq = MagicMock()
#     mock_created_eq.id = 1
#     mock_created_eq.equipment_class = "ClassA"
#     mock_equipment_repo.create_equipment.return_value = mock_created_eq
#     mock_equipment_repo.get_current_emission_factor.return_value = (1, 0.5)

#     # Execute
#     with pytest.raises(ValidationError):
#         await equipment_service.create_equipment(mock_session, data, "user1")
#     # Assert
#     # assert result.id == 1
#     mock_equipment_repo.insert_emission.assert_called_once()


# @pytest.mark.asyncio
# async def test_create_equipment_invalid_power_factor(
#     mock_session, mock_equipment_repo, mock_pf_repo, mock_calc_service
# ):
#     # Setup input
#     data = EquipmentCreateRequest(
#         unit_id="unit1", name="Eq1", submodule="scientific", class_="ClassA"
#     )

#     # Setup Repo Mocks
#     mock_pf_repo.get_power_factor.return_value = None

#     # Execute
#     with pytest.raises(HTTPException) as exc:
#         await equipment_service.create_equipment(mock_session, data, "user1")
#     assert exc.value.status_code == 422


# @pytest.mark.asyncio
# async def test_create_equipment_invalid_equipment_class(
#     mock_session, mock_equipment_repo, mock_pf_repo, mock_calc_service
# ):
#     # Setup input
#     data = EquipmentCreateRequest(
#         unit_id="unit1", name="Eq1", submodule="scientific", class_="InvalidClass"
#     )

#     # Setup Repo Mocks
#     mock_pf = MagicMock(id=10, active_power_w=100, standby_power_w=10)
#     mock_pf_repo.get_power_factor.return_value = mock_pf

#     mock_created_eq = MagicMock()
#     mock_created_eq.id = 1
#     mock_created_eq.equipment_class = "InvalidClass"
#     mock_equipment_repo.create_equipment.return_value = mock_created_eq
#     mock_equipment_repo.get_current_emission_factor.return_value = (1, 0.5)

#     # Execute
#     result = await equipment_service.create_equipment(mock_session, data, "user1")

#     # Assert
#     assert result.id == 1
#     mock_equipment_repo.insert_emission.assert_called_once()


# --- Tests for update_equipment ---


# @pytest.mark.asyncio
# async def test_update_equipment_empty_name(
#     mock_session, mock_equipment_repo, mock_calc_service
# ):
#     # Setup existing
#     existing = MagicMock(id=1, equipment_class="Old")
#     mock_equipment_repo.get_by_id.return_value = existing
#     mock_equipment_repo.update_equipment.return_value = existing
#     mock_equipment_repo.get_current_emission_factor.return_value = (1, 0.5)

#     update_data = EquipmentUpdateRequest(name="")

#     # Execute
#     await equipment_service.update_equipment(mock_session, 1, update_data, "user1")

#     # Assert
#     mock_equipment_repo.retire_current_emission.assert_called_once_with(
# mock_session, 1)


@pytest.mark.asyncio
async def test_update_equipment_invalid_power_factor(
    mock_session, mock_equipment_repo, mock_calc_service
):
    # --- Setup existing equipment ---
    existing = MagicMock(
        id=1,
        name="Eq1",
        equipment_class="Old",
        submodule="scientific",
        status="In service",
        unit_id="unit1",
    )
    mock_equipment_repo.get_by_id.return_value = existing
    mock_equipment_repo.update_equipment.return_value = existing
    mock_equipment_repo.get_current_emission_factor = AsyncMock(return_value=(1, 0.5))
    mock_equipment_repo.get_equipment_with_emissions = AsyncMock(return_value=([], 0))
    mock_equipment_repo.get_equipment_summary_by_submodule = AsyncMock(return_value={})

    # --- Mock PowerFactorRepository to return None asynchronously ---
    mock_pf_repo = MagicMock()
    mock_pf_repo.get_power_factor = AsyncMock(return_value=None)

    with patch(
        "app.services.equipment_service.PowerFactorRepository",
        return_value=mock_pf_repo,
    ):
        update_data = EquipmentUpdateRequest(class_="ClassA")

        # --- Execute & Assert exception ---
        with pytest.raises(HTTPException) as exc:
            await equipment_service.update_equipment(
                mock_session, 1, update_data, "user1"
            )

        assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_update_equipment_invalid_equipment_class(
    mock_session, mock_equipment_repo, mock_calc_service
):
    # --- Setup existing equipment ---
    existing = MagicMock(
        id=1,
        name="Eq1",
        equipment_class="Old",
        submodule="scientific",
        status="In service",
        unit_id="unit1",
    )
    mock_equipment_repo.get_by_id.return_value = existing
    mock_equipment_repo.update_equipment.return_value = existing

    # --- Mock async repo methods ---
    mock_equipment_repo.get_current_emission_factor = AsyncMock(return_value=(1, 0.5))
    mock_equipment_repo.get_equipment_with_emissions = AsyncMock(return_value=([], 0))
    mock_equipment_repo.get_equipment_summary_by_submodule = AsyncMock(return_value={})

    # --- Mock PowerFactorRepository ---
    mock_pf = MagicMock(id=10, active_power_w=100, standby_power_w=10)
    mock_pf_repo = MagicMock()
    mock_pf_repo.get_power_factor = AsyncMock(return_value=mock_pf)

    # Patch PowerFactorRepository
    with patch(
        "app.services.equipment_service.PowerFactorRepository",
        return_value=mock_pf_repo,
    ):
        update_data = EquipmentUpdateRequest(class_="InvalidClass")

        # Patch Pydantic response to avoid validation
        with patch(
            "app.services.equipment_service.EquipmentDetailResponse",
            autospec=True,
        ):
            # --- Execute ---
            await equipment_service.update_equipment(
                mock_session, 1, update_data, "user1"
            )

    # --- Assert ---
    mock_equipment_repo.retire_current_emission.assert_called_once_with(mock_session, 1)


@pytest.mark.asyncio
async def test_update_equipment_empty_sub_class(
    mock_session, mock_equipment_repo, mock_calc_service
):
    # --- Setup existing equipment ---
    existing = MagicMock(
        id=1,
        name="Eq1",
        equipment_class="Old",
        submodule="scientific",
        status="In service",
        unit_id="unit1",
    )
    mock_equipment_repo.get_by_id.return_value = existing
    mock_equipment_repo.update_equipment.return_value = existing

    # --- Mock async repo methods ---
    # get_current_emission_factor returns a tuple (id, value)
    mock_equipment_repo.get_current_emission_factor = AsyncMock(return_value=(1, 0.5))

    # get_equipment_with_emissions returns a tuple (list, total_count)
    mock_equipment_repo.get_equipment_with_emissions = AsyncMock(return_value=([], 0))

    # get_equipment_summary_by_submodule returns a dict
    mock_equipment_repo.get_equipment_summary_by_submodule = AsyncMock(return_value={})

    # --- Mock PowerFactorRepository ---
    mock_pf = MagicMock(id=10, active_power_w=100, standby_power_w=10)
    mock_pf_repo = MagicMock()
    mock_pf_repo.get_power_factor = AsyncMock(return_value=mock_pf)

    # Patch PowerFactorRepository in the service
    with patch(
        "app.services.equipment_service.PowerFactorRepository",
        return_value=mock_pf_repo,
    ):
        # --- Prepare update data ---
        update_data = EquipmentUpdateRequest(sub_class="")

        # Patch Pydantic response to avoid validation errors
        with patch(
            "app.services.equipment_service.EquipmentDetailResponse",
            autospec=True,
        ):
            # --- Execute the service ---
            await equipment_service.update_equipment(
                mock_session, 1, update_data, "user1"
            )

    # --- Assert that emissions were retired ---
    mock_equipment_repo.retire_current_emission.assert_called_once_with(mock_session, 1)


# --- Tests for delete_equipment ---


@pytest.mark.asyncio
async def test_delete_equipment_not_found(mock_session, mock_equipment_repo):
    # Setup
    mock_equipment_repo.get_by_id.return_value = None

    # Execute
    with pytest.raises(HTTPException) as exc:
        await equipment_service.delete_equipment(mock_session, 999, "user1")
    assert exc.value.status_code == 404
