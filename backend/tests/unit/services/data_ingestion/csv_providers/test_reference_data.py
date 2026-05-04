"""Tests for ModulePerYearReferenceDataApiProvider."""

import pytest

from app.models.data_ingestion import EntityType
from app.services.data_ingestion.csv_providers.reference_data import (
    ModulePerYearReferenceDataApiProvider,
)


def _make_provider():
    config = {"job_id": "test", "year": 2024}
    return ModulePerYearReferenceDataApiProvider(config=config)


def test_entity_type():
    provider = _make_provider()
    assert provider.entity_type == EntityType.MODULE_PER_YEAR


@pytest.mark.asyncio
async def test_setup_handlers_and_context():
    provider = _make_provider()
    result = await provider._setup_handlers_and_context()
    assert result == {}
