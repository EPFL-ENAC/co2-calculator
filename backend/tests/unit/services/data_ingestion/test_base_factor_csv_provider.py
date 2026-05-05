"""Tests for BaseFactorCSVProvider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionState
from app.services.data_ingestion import base_factor_csv_provider
from app.services.data_ingestion.base_factor_csv_provider import BaseFactorCSVProvider


class ConcreteFactorProvider(BaseFactorCSVProvider):
    @property
    def entity_type(self) -> EntityType:
        return EntityType.MODULE_PER_YEAR

    async def _setup_handlers_and_context(self):
        return {}


def _build_stats():
    return {
        "rows_processed": 0,
        "rows_skipped": 0,
        "batches_processed": 0,
        "row_errors": [],
        "row_errors_count": 0,
        "factors_deleted": 0,
        "factors_upserted": 0,
    }


def test_resolve_data_entry_type_configured():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": 1},
        data_session=MagicMock(),
    )
    stats = _build_stats()
    setup_result = {"handlers": [], "valid_entry_types": [DataEntryTypeEnum.member]}

    data_entry_type = provider._resolve_data_entry_type(
        row={},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type == DataEntryTypeEnum.member


def test_resolve_data_entry_type_from_id_invalid():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()
    setup_result = {"handlers": [], "valid_entry_types": [DataEntryTypeEnum.member]}

    data_entry_type = provider._resolve_data_entry_type(
        row={"data_entry_type_id": "999"},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type is None
    assert stats["row_errors_count"] == 1


def test_resolve_data_entry_type_from_name_valid():
    handler = MagicMock()
    handler.category_field = "data_entry_type"
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "handlers": [handler]}, data_session=MagicMock()
    )
    stats = _build_stats()
    setup_result = {
        "handlers": [handler],
        "valid_entry_types": [DataEntryTypeEnum.member],
    }

    data_entry_type = provider._resolve_data_entry_type(
        row={"data_entry_type": "member"},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type == DataEntryTypeEnum.member


def test_resolve_data_entry_type_from_name_invalid():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()
    setup_result = {"handlers": [], "valid_entry_types": [DataEntryTypeEnum.member]}

    data_entry_type = provider._resolve_data_entry_type(
        row={"data_entry_type": "not-valid"},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type is None
    assert stats["row_errors_count"] == 1


def test_resolve_data_entry_type_single_valid():
    handler = MagicMock()
    handler.category_field = "data_entry_type"
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "handlers": [handler]}, data_session=MagicMock()
    )
    stats = _build_stats()
    setup_result = {
        "handlers": [handler],
        "valid_entry_types": [DataEntryTypeEnum.member],
    }

    data_entry_type = provider._resolve_data_entry_type(
        row={"data_entry_type": "member"},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type == DataEntryTypeEnum.member


def test_resolve_data_entry_type_missing_multi():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"}, data_session=MagicMock()
    )
    stats = _build_stats()
    setup_result = {
        "handlers": [],
        "valid_entry_types": [DataEntryTypeEnum.member, DataEntryTypeEnum.student],
    }

    data_entry_type = provider._resolve_data_entry_type(
        row={},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type is None
    assert stats["row_errors_count"] == 1


@pytest.mark.asyncio
async def test_process_row_validation_error_records_error(monkeypatch):
    handler = MagicMock()
    handler.category_field = "data_entry_type"
    handler.classification_fields = ["kind"]
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "handlers": [handler]}, data_session=MagicMock()
    )
    stats = _build_stats()

    handler.validate_create.side_effect = ValueError("bad payload")

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )

    # Mock emission type resolution
    monkeypatch.setattr(
        base_factor_csv_provider,
        "get_factor_emission_type_id",
        lambda *args, **kwargs: 10000,
    )

    setup_result = {
        "handlers": [handler],
        "expected_columns": {"data_entry_type", "kind"},
        "valid_entry_types": [DataEntryTypeEnum.member],
    }

    factor, error_msg = await provider._process_row(
        row={"data_entry_type": "member", "kind": "x"},
        row_idx=2,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        factor_service=MagicMock(),
    )

    assert factor is None
    assert "Validation error" in error_msg
    assert stats["rows_skipped"] == 1


@pytest.mark.asyncio
async def test_process_row_success(monkeypatch):
    handler_mock = MagicMock()
    handler_mock.category_field = "data_entry_type"
    handler_mock.classification_fields = ["kind"]
    handler_mock.value_fields = ["value"]
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "year": 2024, "handlers": [handler_mock]},
        data_session=MagicMock(),
    )
    stats = _build_stats()

    handler = MagicMock()
    handler.validate_create.return_value = SimpleNamespace(
        emission_type_id=10,
        is_conversion=False,
        data_entry_type_id=DataEntryTypeEnum.member.value,
        classification={"kind": "x"},
        values={"value": 1.0},
    )

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )

    # Mock emission type resolution
    monkeypatch.setattr(
        base_factor_csv_provider,
        "get_factor_emission_type_id",
        lambda *args, **kwargs: 10000,
    )

    factor_service = MagicMock()
    factor_service.prepare_create = AsyncMock(return_value=SimpleNamespace(id=1))

    setup_result = {
        "handlers": [handler_mock],
        "expected_columns": {"data_entry_type", "kind", "value"},
        "valid_entry_types": [DataEntryTypeEnum.member],
    }

    factor, error_msg = await provider._process_row(
        row={"data_entry_type": "member", "kind": "x", "value": "1.0"},
        row_idx=3,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        factor_service=factor_service,
    )

    assert error_msg is None
    assert factor.id == 1
    factor_service.prepare_create.assert_awaited_once()


def test_validate_csv_headers_strict_missing_expected():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "strict_column_validation": True},
        data_session=MagicMock(),
    )

    csv_text = "col1,col2\nval1,val2"
    expected_columns = {"col1", "col2", "col3"}

    with pytest.raises(ValueError, match="Strict mode"):
        provider._validate_csv_headers(csv_text, expected_columns, set())


@pytest.mark.asyncio
async def test_finalize_and_commit_move_file_failure():
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "job_id": 1, "year": 2024},
        data_session=MagicMock(),
    )
    provider._files_store = MagicMock()
    provider._files_store.move_file = AsyncMock(return_value=False)
    provider.data_session.flush = AsyncMock()

    result = await provider._finalize_and_commit(
        batch=[],
        factor_service=MagicMock(),
        stats=_build_stats(),
        setup_result={"processing_path": "processing/x", "filename": "x.csv"},
        factor_repo=MagicMock(),
    )
    assert result["state"] == IngestionState.FINISHED


# ---------------------------------------------------------------------------
# Tests for _get_types_to_delete
# ---------------------------------------------------------------------------


def test_get_types_to_delete_with_configured_data_entry_type_id():
    """When data_entry_type_id is set, only that single type is returned."""
    provider = ConcreteFactorProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.member.value,
        },
        data_session=MagicMock(),
    )
    listed = [DataEntryTypeEnum.member, DataEntryTypeEnum.student]

    result = provider._get_types_to_delete(listed)

    assert result == [DataEntryTypeEnum.member]


def test_get_types_to_delete_without_data_entry_type_id_returns_all():
    """When data_entry_type_id is not set, all listed types are returned."""
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"},
        data_session=MagicMock(),
    )
    listed = [DataEntryTypeEnum.member, DataEntryTypeEnum.student]

    result = provider._get_types_to_delete(listed)

    assert result == listed


def test_get_types_to_delete_empty_listed_without_id():
    """Empty listed_entry_types results in an empty deletion list."""
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv"},
        data_session=MagicMock(),
    )

    result = provider._get_types_to_delete([])

    assert result == []


def test_get_types_to_delete_subclass_override_restricts_scope():
    """A subclass that overrides _get_types_to_delete can restrict deletion scope."""

    class RestrictedProvider(ConcreteFactorProvider):
        def _get_types_to_delete(
            self, listed_entry_types: list[DataEntryTypeEnum]
        ) -> list[DataEntryTypeEnum]:
            return [DataEntryTypeEnum.member]

    provider = RestrictedProvider(
        {"file_path": "tmp/test.csv"},
        data_session=MagicMock(),
    )
    listed = [
        DataEntryTypeEnum.member,
        DataEntryTypeEnum.student,
        DataEntryTypeEnum.scientific,
    ]

    result = provider._get_types_to_delete(listed)

    assert result == [DataEntryTypeEnum.member]
    assert DataEntryTypeEnum.student not in result
    assert DataEntryTypeEnum.scientific not in result


def test_get_types_to_delete_configured_id_ignores_listed():
    """Configured data_entry_type_id takes priority; listed types are ignored."""
    provider = ConcreteFactorProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": DataEntryTypeEnum.scientific.value,
        },
        data_session=MagicMock(),
    )
    # listed contains types that do NOT include `scientific`
    listed = [DataEntryTypeEnum.member, DataEntryTypeEnum.student]

    result = provider._get_types_to_delete(listed)

    assert result == [DataEntryTypeEnum.scientific]


@pytest.mark.asyncio
async def test_upsert_batch_raises_when_job_id_missing():
    """``_upsert_batch`` requires ``self.job_id`` so each row can be stamped
    with ``last_seen_job_id``.  If the job_id was never set (e.g. the
    seed-script path that bypasses DataIngestionJob creation), raise
    eagerly rather than persist factors with a NULL pointer to "current
    factor job."""
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": 1},
        data_session=MagicMock(),
    )
    # No set_job_id call → self.job_id stays None.
    factor_repo = MagicMock()
    factor_repo.upsert_factors = AsyncMock(return_value=0)

    with pytest.raises(ValueError, match="job_id is required"):
        await provider._upsert_batch([MagicMock()], factor_repo)

    factor_repo.upsert_factors.assert_not_awaited()


@pytest.mark.asyncio
async def test_upsert_batch_falls_back_to_batch_size_when_rowcount_negative():
    """asyncpg returns rowcount=-1 for executemany ON CONFLICT statements
    where it can't tally the result reliably.  ``_upsert_batch`` should
    fall back to the input batch size so operator-visible stats don't
    show a confusing -1."""
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": 1},
        data_session=MagicMock(),
    )
    await provider.set_job_id(42)

    factor_repo = MagicMock()
    factor_repo.upsert_factors = AsyncMock(return_value=-1)

    batch = [MagicMock(), MagicMock(), MagicMock()]
    reported = await provider._upsert_batch(batch, factor_repo)

    assert reported == 3, "negative rowcount should fall back to len(batch)"
