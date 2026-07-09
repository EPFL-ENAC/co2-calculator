"""Tests for FactorCopyProvider (#740)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import IngestionResult, IngestionState
from app.models.factor import Factor
from app.services.data_ingestion.factor_copy_provider import FactorCopyProvider


def _make_provider(
    *,
    data_entry_type_id: int = DataEntryTypeEnum.member.value,
    year: int = 2025,
    job_id: int | None = 99,
) -> FactorCopyProvider:
    provider = FactorCopyProvider(
        config={"data_entry_type_id": data_entry_type_id, "year": year},
        data_session=MagicMock(),
    )
    provider.job_id = job_id
    provider.data_session.flush = AsyncMock()
    return provider


def _make_factor(
    emission_type_id: int = 5,
    classification: dict | None = None,
    values: dict | None = None,
    year: int = 2024,
    factor_id: int = 1,
) -> Factor:
    return Factor(
        id=factor_id,
        emission_type_id=emission_type_id,
        data_entry_type_id=DataEntryTypeEnum.member.value,
        classification=classification or {"kind": "member"},
        values=values or {"factor": 1.23},
        year=year,
    )


@pytest.mark.asyncio
async def test_copies_rows_into_target_year_with_defaulted_source_year():
    """No ``filters.source_year`` → source defaults to ``year - 1``; rows
    are cloned with ``id=None`` and ``year=target_year``."""
    provider = _make_provider(year=2025)
    source_factors = [
        _make_factor(factor_id=1, values={"a": 1}),
        _make_factor(factor_id=2, values={"a": 2}),
    ]

    with (
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorService"
        ) as MockFactorService,
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorRepository"
        ) as MockFactorRepo,
    ):
        MockFactorService.return_value.list_by_data_entry_type = AsyncMock(
            return_value=source_factors
        )
        MockFactorRepo.return_value.upsert_factors = AsyncMock(return_value=2)

        result = await provider.ingest(filters=None)

        # Source lookup used the defaulted year (2025 - 1 = 2024).
        MockFactorService.return_value.list_by_data_entry_type.assert_awaited_once_with(
            data_entry_type_id=DataEntryTypeEnum.member,
            year=2024,
        )

        upsert_call = MockFactorRepo.return_value.upsert_factors.await_args
        cloned = upsert_call.args[0]
        assert upsert_call.kwargs["current_job_id"] == 99
        assert len(cloned) == 2
        for clone, source in zip(cloned, source_factors):
            assert clone.id is None
            assert clone.year == 2025
            assert clone.emission_type_id == source.emission_type_id
            assert clone.classification == source.classification
            assert clone.values == source.values

    assert result["state"] == IngestionState.FINISHED
    assert result["data"]["result"] == IngestionResult.SUCCESS
    assert result["data"]["stats"]["rows_found"] == 2
    assert result["data"]["stats"]["rows_copied"] == 2
    assert result["data"]["stats"]["source_year"] == 2024
    assert result["data"]["stats"]["target_year"] == 2025


@pytest.mark.asyncio
async def test_source_year_override_from_filters():
    """``filters.source_year`` overrides the ``year - 1`` default."""
    provider = _make_provider(year=2025)
    source_factors = [_make_factor(year=2020)]

    with (
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorService"
        ) as MockFactorService,
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorRepository"
        ) as MockFactorRepo,
    ):
        MockFactorService.return_value.list_by_data_entry_type = AsyncMock(
            return_value=source_factors
        )
        MockFactorRepo.return_value.upsert_factors = AsyncMock(return_value=1)

        result = await provider.ingest(filters={"source_year": 2020})

        MockFactorService.return_value.list_by_data_entry_type.assert_awaited_once_with(
            data_entry_type_id=DataEntryTypeEnum.member,
            year=2020,
        )
        cloned = MockFactorRepo.return_value.upsert_factors.await_args.args[0]
        assert cloned[0].year == 2025  # target year, not the source year

    assert result["data"]["stats"]["source_year"] == 2020
    assert result["data"]["stats"]["target_year"] == 2025


@pytest.mark.asyncio
async def test_noops_cleanly_when_source_year_has_no_factors():
    """Source year with zero rows → SUCCESS no-op, no upsert call."""
    provider = _make_provider(year=2025)

    with (
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorService"
        ) as MockFactorService,
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorRepository"
        ) as MockFactorRepo,
    ):
        MockFactorService.return_value.list_by_data_entry_type = AsyncMock(
            return_value=[]
        )
        MockFactorRepo.return_value.upsert_factors = AsyncMock()

        result = await provider.ingest(filters=None)

        MockFactorRepo.return_value.upsert_factors.assert_not_called()

    assert result["state"] == IngestionState.FINISHED
    assert result["data"]["result"] == IngestionResult.SUCCESS
    assert result["data"]["stats"]["rows_found"] == 0
    assert result["data"]["stats"]["rows_copied"] == 0


@pytest.mark.asyncio
async def test_idempotent_on_retry_produces_equivalent_clones():
    """Running the same copy twice (simulating a retry) builds the same
    id-less clone payload both times — safe to re-run because
    ``upsert_factors``'s identity key excludes ``id`` and matches on
    (data_entry_type_id, year, emission_type_id, classification)."""
    source_factors = [_make_factor(factor_id=1, values={"a": 1})]

    calls: list[list[Factor]] = []

    async def _capture_upsert(factors, current_job_id):
        calls.append(factors)
        return len(factors)

    with (
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorService"
        ) as MockFactorService,
        patch(
            "app.services.data_ingestion.factor_copy_provider.FactorRepository"
        ) as MockFactorRepo,
    ):
        MockFactorService.return_value.list_by_data_entry_type = AsyncMock(
            return_value=source_factors
        )
        MockFactorRepo.return_value.upsert_factors = AsyncMock(
            side_effect=_capture_upsert
        )

        provider1 = _make_provider(year=2025)
        await provider1.ingest(filters=None)
        provider2 = _make_provider(year=2025)
        await provider2.ingest(filters=None)

    assert len(calls) == 2
    first, second = calls
    assert len(first) == len(second) == 1
    assert first[0].id is None and second[0].id is None
    assert first[0].year == second[0].year == 2025
    assert first[0].classification == second[0].classification
    assert first[0].values == second[0].values
    assert first[0].emission_type_id == second[0].emission_type_id


@pytest.mark.asyncio
async def test_missing_data_entry_type_id_raises():
    provider = FactorCopyProvider(config={"year": 2025}, data_session=MagicMock())
    provider.job_id = 1
    with pytest.raises(ValueError, match="data_entry_type_id is required"):
        await provider.ingest(filters=None)


@pytest.mark.asyncio
async def test_missing_year_raises():
    provider = FactorCopyProvider(
        config={"data_entry_type_id": DataEntryTypeEnum.member.value},
        data_session=MagicMock(),
    )
    provider.job_id = 1
    with pytest.raises(ValueError, match="year is required"):
        await provider.ingest(filters=None)


@pytest.mark.asyncio
async def test_missing_job_id_raises():
    provider = FactorCopyProvider(
        config={
            "data_entry_type_id": DataEntryTypeEnum.member.value,
            "year": 2025,
        },
        data_session=MagicMock(),
    )
    with pytest.raises(ValueError, match="job_id is required"):
        await provider.ingest(filters=None)
