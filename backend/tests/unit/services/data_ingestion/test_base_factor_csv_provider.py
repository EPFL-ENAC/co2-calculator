"""Tests for BaseFactorCSVProvider."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import EntityType, IngestionState
from app.services.data_ingestion import base_factor_csv_provider
from app.services.data_ingestion.base_factor_csv_provider import BaseFactorCSVProvider


class _DummyFactorPayload(BaseModel):
    """Minimal model used to trigger a real ``pydantic.ValidationError``
    (float/date parsing failures) the same way ``BaseFactorHandler``'s real
    ``create_dto`` would, without depending on the concrete handler."""

    co2_factor: float
    date: datetime.date


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


def test_resolve_data_entry_type_category_exact_case_accepted():
    """equipment_category routing accepts the exact lowercase enum name."""
    handler = MagicMock()
    handler.category_field = "equipment_category"
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "handlers": [handler]}, data_session=MagicMock()
    )
    stats = _build_stats()
    setup_result = {
        "handlers": [handler],
        "valid_entry_types": [DataEntryTypeEnum.scientific],
    }

    data_entry_type = provider._resolve_data_entry_type(
        row={"equipment_category": "scientific"},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type == DataEntryTypeEnum.scientific


def test_resolve_data_entry_type_category_wrong_case_rejected():
    """Doc: equipment_category is case-sensitive — 'Scientific' is rejected."""
    handler = MagicMock()
    handler.category_field = "equipment_category"
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "handlers": [handler]}, data_session=MagicMock()
    )
    stats = _build_stats()
    setup_result = {
        "handlers": [handler],
        "valid_entry_types": [DataEntryTypeEnum.scientific],
    }

    data_entry_type = provider._resolve_data_entry_type(
        row={"equipment_category": "Scientific"},
        setup_result=setup_result,
        row_idx=1,
        stats=stats,
        max_row_errors=5,
    )

    assert data_entry_type is None
    assert stats["row_errors_count"] == 1


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
async def test_process_row_pydantic_validation_error_bad_float(monkeypatch):
    """A bad-float value produces a readable ``field: reason (got value)``
    message instead of pydantic's raw multi-line dump (issue #659)."""
    handler = MagicMock()
    handler.category_field = "data_entry_type"
    handler.classification_fields = ["kind"]
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "handlers": [handler]}, data_session=MagicMock()
    )
    stats = _build_stats()

    def fake_validate_create(payload):
        return _DummyFactorPayload(co2_factor="abc", date=datetime.date(2026, 1, 1))

    handler.validate_create.side_effect = fake_validate_create

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
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
    assert error_msg == (
        "co2_factor: Input should be a valid number, unable to parse "
        "string as a number (got 'abc')"
    )
    assert stats["rows_skipped"] == 1
    assert stats["row_errors"][0]["reason"] == error_msg


@pytest.mark.asyncio
async def test_process_row_pydantic_validation_error_bad_date(monkeypatch):
    """An invalid date produces a readable per-field message (issue #659)."""
    handler = MagicMock()
    handler.category_field = "data_entry_type"
    handler.classification_fields = ["kind"]
    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "handlers": [handler]}, data_session=MagicMock()
    )
    stats = _build_stats()

    def fake_validate_create(payload):
        return _DummyFactorPayload(co2_factor=1.0, date="2026-13-40")

    handler.validate_create.side_effect = fake_validate_create

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
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
        row_idx=3,
        setup_result=setup_result,
        stats=stats,
        max_row_errors=5,
        factor_service=MagicMock(),
    )

    assert factor is None
    assert error_msg.startswith("date: Input should be a valid date or datetime")
    assert "(got '2026-13-40')" in error_msg
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
    provider._files_store.file_exists = AsyncMock(return_value=False)
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


# ---------------------------------------------------------------------------
# #1491 ask 2 — null required identity field guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_row_null_required_identity_field_is_row_error(monkeypatch):
    """A NULL in a DTO-required classification field must be a per-row
    error naming the field — before emission-type resolution and before
    the None can enter the upsert identity key."""
    handler = MagicMock()
    handler.classification_fields = ["kind", "subkind"]
    handler.value_fields = ["value"]
    handler.required_columns = {"kind", "value"}

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    emission_resolver = MagicMock()
    monkeypatch.setattr(
        base_factor_csv_provider, "get_factor_emission_type_id", emission_resolver
    )

    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": 1, "year": 2024},
        data_session=MagicMock(),
    )
    stats = _build_stats()
    factor_service = MagicMock()
    factor_service.prepare_create = AsyncMock()

    factor, error_msg = await provider._process_row(
        row={"kind": "  ", "subkind": "x", "value": "1.0"},
        row_idx=4,
        setup_result={"handlers": [handler], "valid_entry_types": []},
        stats=stats,
        max_row_errors=5,
        factor_service=factor_service,
    )

    assert factor is None
    assert "kind" in error_msg
    assert "Missing required classification field" in error_msg
    assert stats["rows_skipped"] == 1
    assert stats["row_errors"][0]["reason"] == error_msg
    # Guard fires BEFORE emission-type resolution and before any write.
    emission_resolver.assert_not_called()
    factor_service.prepare_create.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_row_null_optional_classification_field_passes(monkeypatch):
    """Handlers with legitimately nullable classification fields (not in
    the DTO's required set) are unaffected by the null-identity guard."""
    handler = MagicMock()
    handler.classification_fields = ["kind", "subkind"]
    handler.value_fields = ["value"]
    handler.required_columns = {"kind", "value"}

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        base_factor_csv_provider,
        "get_factor_emission_type_id",
        lambda *args, **kwargs: 10000,
    )

    provider = ConcreteFactorProvider(
        {"file_path": "tmp/test.csv", "data_entry_type_id": 1, "year": 2024},
        data_session=MagicMock(),
    )
    stats = _build_stats()
    factor_service = MagicMock()
    factor_service.prepare_create = AsyncMock(return_value=SimpleNamespace(id=9))

    factor, error_msg = await provider._process_row(
        row={"kind": "plane", "subkind": "", "value": "1.0"},
        row_idx=5,
        setup_result={"handlers": [handler], "valid_entry_types": []},
        stats=stats,
        max_row_errors=5,
        factor_service=factor_service,
    )

    assert error_msg is None
    assert factor.id == 9
    assert stats["rows_skipped"] == 0


@pytest.mark.asyncio
async def test_null_identity_row_yields_warning_and_no_sweep(monkeypatch):
    """Regression (#1491): a CSV with one null-required-identity row
    finishes WARNING, writes only the good rows, and never sweeps —
    so a bad upload cannot delete factors it failed to re-assert."""
    from app.models.data_ingestion import IngestionResult

    handler = MagicMock()
    handler.classification_fields = ["kind"]
    handler.value_fields = ["value"]
    handler.required_columns = {"kind"}
    handler.validate_create.return_value = None

    monkeypatch.setattr(
        base_factor_csv_provider.BaseFactorHandler,
        "get_by_type",
        MagicMock(return_value=handler),
    )
    monkeypatch.setattr(
        base_factor_csv_provider,
        "get_factor_emission_type_id",
        lambda *args, **kwargs: 10000,
    )

    provider = ConcreteFactorProvider(
        {
            "file_path": "tmp/test.csv",
            "data_entry_type_id": 1,
            "year": 2024,
            "job_id": 7,
        },
        data_session=MagicMock(),
    )
    provider.data_session.flush = AsyncMock()
    provider.data_session.rollback = AsyncMock()
    provider._update_job = AsyncMock()

    csv_text = "kind,value\nplane,1.5\n,2.0\n"

    async def fake_setup():
        return {
            "csv_text": csv_text,
            "handlers": [handler],
            "expected_columns": {"kind", "value"},
            "required_columns": {"kind"},
            "processing_path": "processing/x.csv",
            "filename": "x.csv",
            "valid_entry_types": [DataEntryTypeEnum.member],
        }

    monkeypatch.setattr(provider, "_setup_and_validate", fake_setup)
    monkeypatch.setattr(
        provider, "_move_to_processed", AsyncMock(return_value="processed/x.csv")
    )

    fake_repo = MagicMock()
    fake_repo.upsert_factors = AsyncMock(return_value=1)
    fake_repo.delete_stale_for_year = AsyncMock(return_value=0)
    monkeypatch.setattr(
        base_factor_csv_provider, "FactorRepository", MagicMock(return_value=fake_repo)
    )
    fake_service = MagicMock()
    fake_service.prepare_create = AsyncMock(
        return_value=SimpleNamespace(id=1, data_entry_type_id=1)
    )
    monkeypatch.setattr(
        base_factor_csv_provider, "FactorService", MagicMock(return_value=fake_service)
    )

    result = await provider.process_csv_in_batches()

    assert result["result"] == IngestionResult.WARNING
    assert result["stats"]["rows_processed"] == 1
    assert result["stats"]["rows_skipped"] == 1
    assert result["stats"]["factors_deleted"] == 0
    # Only the good row was written; the null-identity row wrote nothing.
    fake_service.prepare_create.assert_awaited_once()
    # WARNING ⇒ no stale sweep.
    fake_repo.delete_stale_for_year.assert_not_awaited()
