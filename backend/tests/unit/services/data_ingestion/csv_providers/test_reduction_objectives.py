"""Tests for ModulePerYearReductionObjectivesApiProvider."""

import pytest

from app.models.data_ingestion import EntityType
from app.services.data_ingestion.csv_providers.reduction_objectives import (
    ModulePerYearReductionObjectivesApiProvider,
)


def _make_provider(**config_overrides):
    config = {"job_id": "test", "year": 2024, **config_overrides}
    return ModulePerYearReductionObjectivesApiProvider(config=config)


def test_entity_type():
    provider = _make_provider()
    assert provider.entity_type == EntityType.MODULE_PER_YEAR


def test_resolve_handler_missing_type_id():
    provider = _make_provider()
    with pytest.raises(ValueError, match="reduction_objective_type_id is required"):
        provider._resolve_handler()


def test_resolve_handler_valid():
    # ReductionObjectiveType(0) = FOOTPRINT → institutional_footprint
    provider = _make_provider(reduction_objective_type_id=0)
    handler = provider._resolve_handler()
    assert handler is not None
    assert handler.config_key == "institutional_footprint"
