"""Regression tests for the ``BULK_PATH_PURE_ASYNC`` gate on seed runs.

Plan 310-D added a runner-driven ``emission_recalc -> aggregation`` chain
that owns ``data_entry_emissions`` writes and ``carbon_reports.stats``
recomputation when ``BULK_PATH_PURE_ASYNC=True``.  The gate at two sites
in ``base_csv_provider`` (``_process_batch`` post-bulk-create and
``_recompute_module_stats``) short-circuits the inline writes so they
don't race the chain.

Seed scripts run ``LocalDataEntryCSVProvider`` whose ``_update_job`` is a
no-op — the request-scoped CSV ingest handlers never fire, so the chain
never runs.  Without these tests, a bulk_path_pure_async-flagged settings
file would leave seeded modules with empty ``data_entry_emissions`` and
zero stats (broken dev DB bootstrap).

The fix: ``LocalDataEntryCSVProvider`` sets ``self.is_seed_run = True``;
the gate sites honour it and always inline-write for seed runs.  These
tests pin both gate sites under ``BULK_PATH_PURE_ASYNC=True``.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import EntityType
from app.services.data_ingestion.csv_providers.local_seed import (
    LocalDataEntryCSVProvider,
)


def _make_provider() -> LocalDataEntryCSVProvider:
    """Build a ``LocalDataEntryCSVProvider`` with the minimum needed for
    gate-level assertions (no DB, no factor lookup, no rows)."""
    data_session = MagicMock()
    data_session.flush = AsyncMock()
    return LocalDataEntryCSVProvider(
        config={
            "local_file_path": "/tmp/seed.csv",
            "module_type_id": 1,
            "data_entry_type_id": 1,
            "year": 2025,
        },
        data_session=data_session,
    )


def test_local_data_entry_provider_marks_seed_run():
    """``LocalDataEntryCSVProvider`` must set ``is_seed_run=True`` so the
    gate sites in ``base_csv_provider`` honour the seed path."""
    provider = _make_provider()
    assert provider.is_seed_run is True


@pytest.mark.asyncio
async def test_recompute_module_stats_runs_inline_for_seed_run_under_async_gate():
    """Pin gate site 2 (``_recompute_module_stats``).

    Under ``BULK_PATH_PURE_ASYNC=True``, the base implementation logs a
    debug message and returns.  Seed runs must bypass that early return
    so the inline stats recompute still happens — otherwise dev DB
    bootstrap leaves ``carbon_reports.stats`` at zero.
    """
    provider = _make_provider()
    # Force the post-gate body into a controlled, observable path: empty
    # _unit_to_module_map causes the function to log a warning and return
    # AFTER the gate.  That's exactly what we want — it proves the gate
    # didn't short-circuit while keeping the test free of DB plumbing.
    provider._unit_to_module_map = {}

    with (
        patch(
            "app.services.data_ingestion.base_csv_provider.get_settings"
        ) as mock_get_settings,
        patch(
            "app.services.data_ingestion.base_csv_provider.CarbonReportModuleService"
        ) as mock_crm_service_cls,
    ):
        mock_get_settings.return_value = SimpleNamespace(BULK_PATH_PURE_ASYNC=True)
        mock_crm_service_cls.return_value = MagicMock()

        # Sanity-check the gate's view of the entity type.
        assert provider.entity_type == EntityType.MODULE_PER_YEAR

        await provider._recompute_module_stats()

    # If the gate had short-circuited, ``CarbonReportModuleService`` would
    # never have been instantiated.  Its construction proves the function
    # ran past line 1244.
    mock_crm_service_cls.assert_called_once_with(provider.data_session)


@pytest.mark.asyncio
async def test_recompute_module_stats_short_circuits_for_non_seed_under_async_gate():
    """Negative control: the gate must STILL short-circuit non-seed
    providers under ``BULK_PATH_PURE_ASYNC=True``.  Without this control
    the previous test could pass for the wrong reason (e.g. someone
    deletes the gate entirely)."""
    provider = _make_provider()
    # Flip the seed marker to simulate a regular runner-driven provider.
    provider.is_seed_run = False
    provider._unit_to_module_map = {}

    with (
        patch(
            "app.services.data_ingestion.base_csv_provider.get_settings"
        ) as mock_get_settings,
        patch(
            "app.services.data_ingestion.base_csv_provider.CarbonReportModuleService"
        ) as mock_crm_service_cls,
    ):
        mock_get_settings.return_value = SimpleNamespace(BULK_PATH_PURE_ASYNC=True)
        await provider._recompute_module_stats()

    # Gate short-circuited — service was never constructed.
    mock_crm_service_cls.assert_not_called()


@pytest.mark.asyncio
async def test_process_batch_inline_emissions_run_for_seed_run_under_async_gate():
    """Pin gate site 1 (``_process_batch`` post-bulk-create).

    Under ``BULK_PATH_PURE_ASYNC=True`` the base implementation returns
    after ``data_entry_service.bulk_create`` and lets the runner chain
    create emissions.  Seed runs must bypass that return so emissions
    are written inline — otherwise ``data_entry_emissions`` stays empty
    after seeding.
    """
    provider = _make_provider()

    # Mock data entry service: returns one response with id=42 so the
    # post-gate code has something to iterate over.
    data_entry_response = SimpleNamespace(id=42)
    data_entry_service = MagicMock()
    data_entry_service.bulk_create = AsyncMock(return_value=[data_entry_response])

    # Mock emission service: prepare_create returns a single emission obj.
    emission_obj = MagicMock()
    emission_service = MagicMock()
    emission_service.prepare_create = AsyncMock(return_value=[emission_obj])
    emission_service.bulk_create = AsyncMock()

    # Build a minimal batch — _process_batch only needs entries with
    # carbon_report_module_id (or None) and any object shape.  Use one
    # entry with no module id to skip the year-cache pre-fetch.
    batch_entry = SimpleNamespace(carbon_report_module_id=None)

    with patch(
        "app.services.data_ingestion.base_csv_provider.get_settings"
    ) as mock_get_settings:
        mock_get_settings.return_value = SimpleNamespace(BULK_PATH_PURE_ASYNC=True)
        await provider._process_batch(
            batch=[batch_entry],
            data_entry_service=data_entry_service,
            emission_service=emission_service,
            user=None,
            batch_kg_co2eq_overrides=[None],
        )

    # bulk_create on data_entry_service ran (pre-gate); critical
    # post-gate calls must have run too because is_seed_run bypasses
    # the early return.
    data_entry_service.bulk_create.assert_awaited_once()
    emission_service.prepare_create.assert_awaited_once()
    emission_service.bulk_create.assert_awaited_once_with([emission_obj])


@pytest.mark.asyncio
async def test_process_batch_short_circuits_for_non_seed_under_async_gate():
    """Negative control for gate site 1.  Non-seed providers must still
    short-circuit so the runner-driven chain owns the emission writes."""
    provider = _make_provider()
    provider.is_seed_run = False

    data_entry_service = MagicMock()
    data_entry_service.bulk_create = AsyncMock(return_value=[SimpleNamespace(id=42)])

    emission_service = MagicMock()
    emission_service.prepare_create = AsyncMock()
    emission_service.bulk_create = AsyncMock()

    batch_entry = SimpleNamespace(carbon_report_module_id=None)

    with patch(
        "app.services.data_ingestion.base_csv_provider.get_settings"
    ) as mock_get_settings:
        mock_get_settings.return_value = SimpleNamespace(BULK_PATH_PURE_ASYNC=True)
        await provider._process_batch(
            batch=[batch_entry],
            data_entry_service=data_entry_service,
            emission_service=emission_service,
            user=None,
            batch_kg_co2eq_overrides=[None],
        )

    # Pre-gate work happened; post-gate work did NOT.
    data_entry_service.bulk_create.assert_awaited_once()
    emission_service.prepare_create.assert_not_awaited()
    emission_service.bulk_create.assert_not_awaited()
