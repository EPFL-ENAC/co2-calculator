"""Unit test for POST /v1/sync/factors/{module}/{det} accepting the
``copy_previous_year`` ingestion method (#740).

Calls the endpoint function directly (not through TestClient/ASGI) with
mocked collaborators — ``ProviderFactory.create_provider``,
``_stamp_job_type_and_meta``, ``fire_and_forget``/``run_job``, and the
request-context extractors — so this stays a fast unit test rather than
requiring a real Postgres (see the ``_pg`` integration suite for the
full-stack round trip of other sync endpoints).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import data_sync
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionMethod, TargetType
from app.models.module_type import ModuleTypeEnum


@pytest.mark.asyncio
async def test_sync_module_factors_accepts_copy_previous_year_with_source_year_filter():
    """``ingestion_method=copy_previous_year`` + ``filters.source_year``
    is accepted, dispatched to ``ProviderFactory.create_provider`` with the
    new method, and the filter is threaded into the job's stamped meta —
    the same ``meta["filters"]`` slot ``factor_ingest_handler`` reads at
    run time to call ``provider.ingest(filters)``.
    """
    sync_request = data_sync.SyncRequest(
        ingestion_method=IngestionMethod.copy_previous_year,
        target_type=TargetType.FACTORS,
        year=2025,
        filters={"source_year": 2020},
    )

    mock_provider = MagicMock()
    mock_provider.validate_connection = AsyncMock(return_value=True)
    mock_provider.create_job = AsyncMock(return_value=42)
    type(mock_provider).__name__ = "FactorCopyProvider"

    db = MagicMock()
    db.commit = AsyncMock()

    with (
        patch.object(
            data_sync.ProviderFactory,
            "create_provider",
            AsyncMock(return_value=mock_provider),
        ) as mock_create_provider,
        patch.object(data_sync, "_stamp_job_type_and_meta", AsyncMock()) as mock_stamp,
        patch.object(data_sync, "run_job", MagicMock(return_value="job-coro")),
        patch.object(data_sync, "fire_and_forget", MagicMock()),
        patch.object(data_sync, "extract_ip_address", return_value="127.0.0.1"),
        patch.object(data_sync, "extract_route_payload", AsyncMock(return_value=None)),
    ):
        response = await data_sync.sync_module_factors(
            module_type_id=ModuleTypeEnum.headcount,
            data_entry_type_id=DataEntryTypeEnum.member,
            syncRequest=sync_request,
            request=MagicMock(),
            background_tasks=MagicMock(),
            db=db,
            current_user=MagicMock(),
        )

    assert response["job_id"] == 42

    # Provider selection was dispatched with the new ingestion method,
    # scoped to the requested module/data-entry type.
    _, create_kwargs = mock_create_provider.call_args
    assert create_kwargs["ingestion_method"] == IngestionMethod.copy_previous_year
    assert create_kwargs["target_type"] == TargetType.FACTORS
    assert (
        create_kwargs["config"]["data_entry_type_id"] == DataEntryTypeEnum.member.value
    )
    assert create_kwargs["config"]["module_type_id"] == ModuleTypeEnum.headcount

    # filters.source_year is threaded through to the job's stamped meta.
    _, stamp_kwargs = mock_stamp.call_args
    assert stamp_kwargs["extra_meta"] == {"filters": {"source_year": 2020}}
    assert stamp_kwargs["job_type"] == "factor_ingest"

    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_module_factors_copy_previous_year_defaults_filters_to_empty_dict():
    """No ``filters`` on the request → stamped meta gets ``{}``, which the
    provider interprets as "use ``year - 1``" (see FactorCopyProvider)."""
    sync_request = data_sync.SyncRequest(
        ingestion_method=IngestionMethod.copy_previous_year,
        target_type=TargetType.FACTORS,
        year=2025,
    )

    mock_provider = MagicMock()
    mock_provider.validate_connection = AsyncMock(return_value=True)
    mock_provider.create_job = AsyncMock(return_value=7)

    db = MagicMock()
    db.commit = AsyncMock()

    with (
        patch.object(
            data_sync.ProviderFactory,
            "create_provider",
            AsyncMock(return_value=mock_provider),
        ),
        patch.object(data_sync, "_stamp_job_type_and_meta", AsyncMock()) as mock_stamp,
        patch.object(data_sync, "run_job", MagicMock(return_value="job-coro")),
        patch.object(data_sync, "fire_and_forget", MagicMock()),
        patch.object(data_sync, "extract_ip_address", return_value="127.0.0.1"),
        patch.object(data_sync, "extract_route_payload", AsyncMock(return_value=None)),
    ):
        response = await data_sync.sync_module_factors(
            module_type_id=ModuleTypeEnum.headcount,
            data_entry_type_id=DataEntryTypeEnum.member,
            syncRequest=sync_request,
            request=MagicMock(),
            background_tasks=MagicMock(),
            db=db,
            current_user=MagicMock(),
        )

    assert response["job_id"] == 7
    _, stamp_kwargs = mock_stamp.call_args
    assert stamp_kwargs["extra_meta"] == {"filters": {}}
