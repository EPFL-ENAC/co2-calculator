"""Tests for ProviderFactory."""

from unittest.mock import MagicMock

import pytest

from app.models.data_ingestion import EntityType, IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.services.data_ingestion.csv_providers import (
    ModulePerYearCSVProvider,
    ModuleUnitSpecificCSVProvider,
)
from app.services.data_ingestion.provider_factory import ProviderFactory


def test_get_provider_class_returns_class():
    provider_class = ProviderFactory.get_provider_class("ModulePerYearCSVProvider")
    assert provider_class is ModulePerYearCSVProvider


def test_get_provider_by_keys_returns_class():
    provider_class = ProviderFactory.get_provider_by_keys(
        ModuleTypeEnum.headcount,
        IngestionMethod.csv,
        TargetType.DATA_ENTRIES,
        EntityType.MODULE_UNIT_SPECIFIC,
    )
    assert provider_class is ModuleUnitSpecificCSVProvider


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
