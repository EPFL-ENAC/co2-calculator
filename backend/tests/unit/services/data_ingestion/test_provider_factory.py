"""Tests for ProviderFactory."""

from unittest.mock import MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.services.data_ingestion.api_providers.professional_travel_api_provider import (
    ProfessionalTravelApiProvider,
)
from app.services.data_ingestion.computed_providers.research_facilities_animal import (
    ResearchFacilitiesAnimalFactorUpdateProvider,
)
from app.services.data_ingestion.computed_providers.research_facilities_common import (
    ResearchFacilitiesCommonFactorUpdateProvider,
)
from app.services.data_ingestion.csv_providers import (
    ModulePerYearCSVProvider,
    ModuleUnitSpecificCSVProvider,
)
from app.services.data_ingestion.provider_factory import ProviderFactory


def test_get_provider_class_returns_class():
    provider_class = ProviderFactory.get_provider_class("ModulePerYearCSVProvider")
    assert provider_class is ModulePerYearCSVProvider


def test_get_provider_class_unknown():
    provider_class = ProviderFactory.get_provider_class("UnknownProvider")
    assert provider_class is None


def test_get_provider_by_keys_returns_class():
    provider_class = ProviderFactory.get_provider_by_keys(
        ModuleTypeEnum.headcount,
        IngestionMethod.csv,
        TargetType.DATA_ENTRIES,
        EntityType.MODULE_UNIT_SPECIFIC,
    )
    assert provider_class is ModuleUnitSpecificCSVProvider


def test_get_provider_by_keys_api_provider():
    provider_class = ProviderFactory.get_provider_by_keys(
        ModuleTypeEnum.professional_travel,
        IngestionMethod.api,
        TargetType.DATA_ENTRIES,
        EntityType.MODULE_PER_YEAR,
    )
    assert provider_class is ProfessionalTravelApiProvider


@pytest.mark.asyncio
async def test_create_provider_valid_entity_type():
    config = {"entity_type": EntityType.MODULE_PER_YEAR.value}
    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum.headcount,
        ingestion_method=IngestionMethod.csv,
        target_type=TargetType.DATA_ENTRIES,
        config=config,
        user=MagicMock(spec=User),
        job_session=None,
        data_session=MagicMock(),
    )

    assert isinstance(provider, ModulePerYearCSVProvider)


@pytest.mark.asyncio
async def test_create_provider_missing_entity_type():
    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum.headcount,
        ingestion_method=IngestionMethod.csv,
        target_type=TargetType.DATA_ENTRIES,
        config={},
        user=MagicMock(spec=User),
        job_session=None,
        data_session=MagicMock(),
    )

    assert provider is None


@pytest.mark.asyncio
async def test_create_provider_invalid_entity_type():
    config = {"entity_type": "not-valid"}
    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum.headcount,
        ingestion_method=IngestionMethod.csv,
        target_type=TargetType.DATA_ENTRIES,
        config=config,
        user=MagicMock(spec=User),
        job_session=None,
        data_session=MagicMock(),
    )

    assert provider is None


@pytest.mark.asyncio
async def test_create_provider_no_matching_provider():
    config = {"entity_type": EntityType.MODULE_PER_YEAR.value}
    provider = await ProviderFactory.create_provider(
        module_type_id=ModuleTypeEnum.headcount,
        ingestion_method=IngestionMethod.api,
        target_type=TargetType.DATA_ENTRIES,
        config=config,
        user=MagicMock(spec=User),
        job_session=None,
        data_session=MagicMock(),
    )

    assert provider is None


def test_get_provider_by_keys_animal_computed_5tuple():
    """5-tuple lookup for mice_and_fish → AnimalFactorUpdateProvider."""
    provider_class = ProviderFactory.get_provider_by_keys(
        ModuleTypeEnum.research_facilities,
        IngestionMethod.computed,
        TargetType.FACTORS,
        EntityType.MODULE_PER_YEAR,
        data_entry_type_id=DataEntryTypeEnum.mice_and_fish_animal_facilities,
    )
    assert provider_class is ResearchFacilitiesAnimalFactorUpdateProvider


def test_get_provider_by_keys_common_computed_5tuple():
    """5-tuple lookup for research_facilities (DE=70) → CommonFactorUpdateProvider."""
    provider_class = ProviderFactory.get_provider_by_keys(
        ModuleTypeEnum.research_facilities,
        IngestionMethod.computed,
        TargetType.FACTORS,
        EntityType.MODULE_PER_YEAR,
        data_entry_type_id=DataEntryTypeEnum.research_facilities,
    )
    assert provider_class is ResearchFacilitiesCommonFactorUpdateProvider


def test_providers_by_class_name_includes_computed_providers():
    """PROVIDERS_BY_CLASS_NAME dict exposes both computed provider classes."""
    assert (
        ProviderFactory.PROVIDERS_BY_CLASS_NAME.get(
            "ResearchFacilitiesAnimalFactorUpdateProvider"
        )
        is ResearchFacilitiesAnimalFactorUpdateProvider
    )
    assert (
        ProviderFactory.PROVIDERS_BY_CLASS_NAME.get(
            "ResearchFacilitiesCommonFactorUpdateProvider"
        )
        is ResearchFacilitiesCommonFactorUpdateProvider
    )
