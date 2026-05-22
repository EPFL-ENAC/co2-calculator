"""Tests for ModulePerYearReductionObjectivesApiProvider."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_ingestion import EntityType
from app.models.user import UserProvider
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


# ---------------------------------------------------------------------------
# Regression: ``_store_in_year_config`` must resolve provider from the
# job context (config["provider"]) when invoked via the runner.
#
# The runner instantiates the CSV provider with ``user=None`` (job rows
# have no ``user`` FK), so the provider cannot fall back to
# ``self.user.provider``. The job's provider IS available via
# ``config["provider"]`` because ``_run_ingest`` spreads ``job.__dict__``
# into config. Earlier we required ``self.user`` to be non-None — that
# broke reduction-objective CSV uploads in production
# (#1266 follow-up: "ValueError: user is required to resolve the
# provider-scoped year_configuration").
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_in_year_config_reads_provider_from_config_when_no_user():
    """Runner path: ``user=None`` but ``config["provider"]`` is the job's
    provider. The SELECT must filter by that provider; no ValueError."""
    provider = _make_provider(
        reduction_objective_type_id=0,
        provider=UserProvider.TEST,
    )
    provider.user = None

    yc_row = MagicMock()
    yc_row.config = {}
    exec_result = MagicMock()
    exec_result.first = MagicMock(return_value=yc_row)
    provider.data_session = MagicMock()
    provider.data_session.exec = AsyncMock(return_value=exec_result)
    provider.data_session.flush = AsyncMock()

    # Should not raise — provider resolved from config["provider"].
    await provider._store_in_year_config(
        validated_rows=[{"x": 1}],
        config_key="institutional_footprint",
        filename="test.csv",
    )
    assert provider.data_session.exec.await_count == 1
    # YC row's reduction_objectives slot was populated.
    assert yc_row.config["reduction_objectives"]["institutional_footprint"] == [
        {"x": 1}
    ]


@pytest.mark.asyncio
async def test_store_in_year_config_falls_back_to_user_provider():
    """Endpoint-driven path: ``config["provider"]`` absent but
    ``self.user.provider`` is set. Fallback must work."""
    provider = _make_provider(reduction_objective_type_id=0)
    user = MagicMock()
    user.provider = UserProvider.ACCRED
    provider.user = user

    yc_row = MagicMock()
    yc_row.config = {}
    exec_result = MagicMock()
    exec_result.first = MagicMock(return_value=yc_row)
    provider.data_session = MagicMock()
    provider.data_session.exec = AsyncMock(return_value=exec_result)
    provider.data_session.flush = AsyncMock()

    await provider._store_in_year_config(
        validated_rows=[],
        config_key="institutional_footprint",
        filename="test.csv",
    )
    assert provider.data_session.exec.await_count == 1


@pytest.mark.asyncio
async def test_store_in_year_config_raises_when_provider_missing_everywhere():
    """Neither ``config["provider"]`` nor ``self.user`` available — must
    raise so callers see the bug instead of silently writing to a
    DEFAULT-scoped row."""
    provider = _make_provider(reduction_objective_type_id=0)
    provider.user = None
    provider.data_session = MagicMock()

    with pytest.raises(ValueError, match="provider is required"):
        await provider._store_in_year_config(
            validated_rows=[],
            config_key="institutional_footprint",
            filename="test.csv",
        )
