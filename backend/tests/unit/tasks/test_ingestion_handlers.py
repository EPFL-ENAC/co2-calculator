"""Unit tests for the Plan 310-C ingestion handlers.

Pins the contract for ``csv_ingest_handler`` / ``api_ingest_handler``
/ ``factor_ingest_handler``:

- Registration via the @register decorator (registry smoke).
- Provider class resolved from ``meta.provider_name``; ValueError if
  missing or unknown so the runner records FINISHED+ERROR.
- ``provider.ingest()`` is awaited with ``meta.filters``; the handler
  returns the meta dict the runner persists alongside the
  FINISHED-state write (status_message + result + the ingest summary).
- ``factor_ingest_handler``'s post-success block fans out one
  ``chain_job`` call per stale (module, det) — replaces 310-B's
  ``_enqueue_stale_recalculations`` in-process.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_ingestion import IngestionResult
from app.tasks import ingestion_tasks as ingest_mod
from app.tasks.registry import _REGISTRY, get_handler


@pytest.fixture(autouse=True)
def _registry_snapshot():
    """Snapshot+restore the registry so tests don't bleed across files.

    Also stub the #1530 status bump: it issues real DB I/O against
    ``data_session`` on the success arm, but these handler tests drive
    MagicMock sessions and assert on the ``_run_ingest`` / fan-out
    contract only.  The bump is covered directly against a real session
    in ``test_carbon_report_service.py``.
    """
    snapshot = dict(_REGISTRY)
    with patch.object(
        ingest_mod,
        "_mark_modules_in_progress_for_data_ingest",
        new_callable=AsyncMock,
    ):
        yield
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)


def _make_job(
    *,
    job_id: int = 1,
    module_type_id: int | None = 11,
    data_entry_type_id: int | None = 22,
    year: int | None = 2025,
    target_type=None,
    meta: dict | None = None,
) -> MagicMock:
    job = MagicMock()
    job.id = job_id
    job.module_type_id = module_type_id
    job.data_entry_type_id = data_entry_type_id
    job.year = year
    job.target_type = target_type
    job.meta = meta or {}
    job.user = None
    # ``job.__dict__`` is read by ``_run_ingest`` to build the
    # provider config; MagicMock's __dict__ is fine — providers index
    # specific keys via dict.get/[] with their own defaults.
    return job


# ---------------------------------------------------------------------------
# Registration smoke
# ---------------------------------------------------------------------------


def test_csv_ingest_registered():
    assert get_handler("csv_ingest") is ingest_mod.csv_ingest_handler


def test_api_ingest_registered():
    assert get_handler("api_ingest") is ingest_mod.api_ingest_handler


def test_factor_ingest_registered():
    assert get_handler("factor_ingest") is ingest_mod.factor_ingest_handler


# ---------------------------------------------------------------------------
# Shared _run_ingest contract — exercised through csv_ingest_handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csv_ingest_handler_resolves_provider_and_returns_meta():
    """Happy path: provider resolved from ``meta.provider_name``,
    ``provider.ingest`` called once, handler returns the meta dict
    with status_message + result + ingest summary.  Plan 310-D adds
    a single ``emission_recalc`` chain on the success arm — patched
    out here since the assertions focus on the run_ingest contract."""
    job = _make_job(meta={"provider_name": "FakeCSV", "config": {"foo": "bar"}})
    job_session = MagicMock()
    data_session = MagicMock()

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "Success",
            "data": {"result": IngestionResult.SUCCESS, "inserted": 7},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock),
    ):
        meta = await ingest_mod.csv_ingest_handler(job, job_session, data_session)

    fake_provider.set_job_id.assert_awaited_once_with(1)
    fake_provider.ingest.assert_awaited_once()
    assert meta["status_message"] == "Success"
    assert meta["result"] == IngestionResult.SUCCESS
    assert meta["inserted"] == 7


@pytest.mark.asyncio
async def test_csv_ingest_error_result_does_not_report_success():
    """#1236 root cause: ``ingest()`` hardcodes status_message='Success'
    when it doesn't raise, but a CSV where every row errored finishes
    WITHOUT raising and is classified ERROR. A FINISHED job whose
    result != SUCCESS must NOT claim 'Success' (jobs 2/49/50/51 shape).
    """
    job = _make_job(meta={"provider_name": "FakeCSV", "config": {}})
    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "Success",  # the hardcoded ingest() lie
            "data": {
                "result": IngestionResult.ERROR,
                "inserted": 0,
                "skipped": 50072,
            },
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock),
    ):
        meta = await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())

    assert meta["result"] == IngestionResult.ERROR
    assert meta["status_message"] != "Success"
    assert "Success" not in meta["status_message"]
    assert meta["status_message"] == "ERROR: 0 inserted, 50072 skipped"


# ---------------------------------------------------------------------------
# Lone-orphan ``last_error`` improvement (#1236 follow-up) —
# ``finalize_ingest_meta`` enriches the honest summary with the first
# row_error's reason so a pipeline-of-one parent doesn't surface as just
# "ERROR: 0 inserted, 50 072 skipped" with no clue WHY.
# ---------------------------------------------------------------------------


def test_finalize_ingest_meta_enriches_with_first_row_error_reason():
    """Every row failed with the same reason → status_message carries
    a sample of that reason so the operator doesn't have to expand the
    timeline to find the cause."""
    result = {
        "status_message": "Success",  # the ingest() lie
        "data": {
            "result": IngestionResult.ERROR,
            "inserted": 0,
            "skipped": 50072,
            "row_errors": [
                {
                    "row": 1,
                    "reason": (
                        "No matching factor found in factors map "
                        "(kind=Monitors, subkind=None)"
                    ),
                },
                {"row": 2, "reason": "same"},
            ],
        },
    }

    meta = ingest_mod.finalize_ingest_meta(result)

    assert meta["status_message"].startswith(
        "ERROR: 0 inserted, 50072 skipped — first error: "
    )
    assert "kind=Monitors" in meta["status_message"]


def test_finalize_ingest_meta_caps_long_reason():
    """A 600-char reason (e.g. a Postgres traceback) must not bloat the
    status_message column — capped at ~200 chars with an ellipsis."""
    long_reason = "x" * 600
    result = {
        "status_message": "Success",
        "data": {
            "result": IngestionResult.ERROR,
            "inserted": 0,
            "skipped": 50000,
            "row_errors": [{"row": 1, "reason": long_reason}],
        },
    }

    meta = ingest_mod.finalize_ingest_meta(result)
    suffix = meta["status_message"].split("first error: ", 1)[1]

    # 200-char cap (199 chars + "…"); proves the message stays small
    # even when the underlying reason is multi-KB.
    assert len(suffix) <= 201
    assert suffix.endswith("…")


def test_finalize_ingest_meta_no_row_errors_keeps_short_summary():
    """When row_errors is absent (e.g. setup-time fail-fast guard fired
    before the row loop), the message keeps the count-only summary —
    no spurious 'first error: None' appended."""
    result = {
        "status_message": "Success",
        "data": {
            "result": IngestionResult.ERROR,
            "inserted": 0,
            "skipped": 0,
        },
    }
    meta = ingest_mod.finalize_ingest_meta(result)
    assert meta["status_message"] == "ERROR: 0 inserted, 0 skipped"
    assert "first error" not in meta["status_message"]


def test_finalize_ingest_meta_success_path_preserved():
    """A genuine SUCCESS keeps its original status_message regardless
    of row_errors content (defensive: row_errors should be empty on
    SUCCESS, but if a provider still recorded warnings we don't lie
    about a failure)."""
    result = {
        "status_message": "Success",
        "data": {
            "result": IngestionResult.SUCCESS,
            "inserted": 100,
            "skipped": 0,
            "row_errors": [{"row": 99, "reason": "warn"}],
        },
    }
    meta = ingest_mod.finalize_ingest_meta(result)
    assert meta["status_message"] == "Success"


@pytest.mark.asyncio
async def test_api_ingest_handler_uses_same_path():
    """``api_ingest_handler`` shares ``_run_ingest`` — same contract."""
    job = _make_job(meta={"provider_name": "FakeAPI"})
    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "ok",
            "data": {"result": IngestionResult.SUCCESS},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock),
    ):
        meta = await ingest_mod.api_ingest_handler(job, MagicMock(), MagicMock())

    assert meta["result"] == IngestionResult.SUCCESS


@pytest.mark.asyncio
async def test_csv_ingest_handler_raises_when_provider_name_missing():
    """No ``meta.provider_name`` → ValueError so the runner stamps
    FINISHED+ERROR with a clear message."""
    job = _make_job(meta={})
    with pytest.raises(ValueError, match="missing meta.provider_name"):
        await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_csv_ingest_handler_raises_when_provider_class_unknown():
    """ProviderFactory returns None → ValueError; runner marks ERROR."""
    job = _make_job(meta={"provider_name": "UnknownProvider"})
    with patch.object(
        ingest_mod.ProviderFactory, "get_provider_class", return_value=None
    ):
        with pytest.raises(ValueError, match="provider class .* not found"):
            await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# factor_ingest post-success fan-out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_factor_ingest_handler_chains_recalc_for_single_type():
    """Parent has both module + det set → exactly one chain_job for
    that pair (single-type factor upload — bypasses
    ``get_recalculation_status_by_year``)."""
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        meta={"provider_name": "FakeFactor"},
    )

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "Factors upserted",
            "data": {"result": IngestionResult.SUCCESS, "upsert_count": 3},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.factor_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_awaited_once()
    chain_kwargs = mock_chain.await_args.kwargs
    assert chain_kwargs["job_type"] == "emission_recalc"
    assert chain_kwargs["module_type_id"] == 5
    assert chain_kwargs["data_entry_type_id"] == 11
    assert chain_kwargs["year"] == 2025
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired
    assert meta["upsert_count"] == 3


@pytest.mark.asyncio
async def test_factor_ingest_handler_chains_per_det_for_multitype_upload():
    """Parent has module set, det=NULL → expand via
    MODULE_TYPE_TO_DATA_ENTRY_TYPES (multi-type factor file).  The repo's
    recalc-status query MUST NOT be consulted here (it filters on
    state=FINISHED, would silently drop a still-RUNNING parent)."""
    from app.models.module_type import (
        MODULE_TYPE_TO_DATA_ENTRY_TYPES,
        ModuleTypeEnum,
    )

    # Pick a module type with multiple dets.  ``headcount`` → [member, student].
    module = ModuleTypeEnum.headcount
    expected_dets = [d.value for d in MODULE_TYPE_TO_DATA_ENTRY_TYPES[module]]

    job = _make_job(
        module_type_id=module.value,
        data_entry_type_id=None,
        year=2025,
        meta={"provider_name": "FakeFactor"},
    )

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "ok",
            "data": {"result": IngestionResult.SUCCESS},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.factor_ingest_handler(job, MagicMock(), MagicMock())

    assert mock_chain.await_count == len(expected_dets)
    chained_dets = {c.kwargs["data_entry_type_id"] for c in mock_chain.await_args_list}
    assert chained_dets == set(expected_dets)
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired


@pytest.mark.asyncio
async def test_factor_ingest_handler_skips_fan_out_on_error():
    """If the ingest itself errored, no recalc fan-out — there's
    nothing to recompute against, and the parent will be marked
    FINISHED+ERROR by the runner."""
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        meta={"provider_name": "FakeFactor"},
    )

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "validation failed",
            "data": {"result": IngestionResult.ERROR},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.factor_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_not_awaited()
    assert meta["result"] == IngestionResult.ERROR
    assert "recalc_jobs_chained" not in meta


@pytest.mark.asyncio
async def test_factor_ingest_handler_skips_fan_out_when_year_missing():
    """A factor job with no year can't choose a recalc scope; log and
    skip rather than raise (the parent ingest itself succeeded)."""
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=None,
        meta={"provider_name": "FakeFactor"},
    )

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "ok",
            "data": {"result": IngestionResult.SUCCESS},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.factor_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_not_awaited()
    assert meta["result"] == IngestionResult.SUCCESS
    assert "recalc_jobs_chained" not in meta


@pytest.mark.asyncio
async def test_factor_ingest_handler_consults_repo_when_module_and_det_both_null():
    """Both NULL — admin-style "anything stale" trigger.  Reads from
    ``get_recalculation_status_by_year`` (filters to needs_recalculation
    only)."""
    job = _make_job(
        module_type_id=None,
        data_entry_type_id=None,
        year=2025,
        meta={"provider_name": "FakeFactor"},
    )

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "ok",
            "data": {"result": IngestionResult.SUCCESS},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    repo = MagicMock()
    repo.get_recalculation_status_by_year = AsyncMock(
        return_value=[
            {
                "module_type_id": 1,
                "data_entry_type_id": 10,
                "year": 2025,
                "needs_recalculation": True,
            },
            {
                "module_type_id": 2,
                "data_entry_type_id": 20,
                "year": 2025,
                "needs_recalculation": False,
            },
        ]
    )

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "DataIngestionRepository", return_value=repo),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.factor_ingest_handler(job, MagicMock(), MagicMock())

    # Only the needs_recalculation=True row was chained.
    mock_chain.assert_awaited_once()
    chain_kwargs = mock_chain.await_args.kwargs
    assert chain_kwargs["module_type_id"] == 1
    assert chain_kwargs["data_entry_type_id"] == 10
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired


@pytest.mark.asyncio
async def test_factor_ingest_handler_skips_unknown_module_type_in_multitype():
    """Multi-type fan-out with an unknown ``module_type_id`` (e.g. an
    enum value that no longer exists after a deletion) MUST skip rather
    than raise — the parent factor job already finished; we don't want
    to take the calling code down with a ValueError."""
    job = _make_job(
        module_type_id=99999,  # not a valid ModuleTypeEnum value
        data_entry_type_id=None,
        year=2025,
        meta={"provider_name": "FakeFactor"},
    )

    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    fake_provider.ingest = AsyncMock(
        return_value={
            "status_message": "ok",
            "data": {"result": IngestionResult.SUCCESS},
        }
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    with (
        patch.object(
            ingest_mod.ProviderFactory,
            "get_provider_class",
            return_value=FakeProviderClass,
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.factor_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_not_awaited()
    assert meta["result"] == IngestionResult.SUCCESS


# ---------------------------------------------------------------------------
# Plan 310-D — csv_ingest / api_ingest post-success emission_recalc fan-out
# ---------------------------------------------------------------------------


def _patch_provider(success: bool = True, *, extra_data: dict | None = None):
    """Build a provider mock + patcher pair returning SUCCESS or ERROR."""
    fake_provider = MagicMock()
    fake_provider.set_job_id = AsyncMock()
    data: dict = {
        "result": IngestionResult.SUCCESS if success else IngestionResult.ERROR
    }
    if extra_data:
        data.update(extra_data)
    fake_provider.ingest = AsyncMock(
        return_value={"status_message": "ok", "data": data}
    )

    class FakeProviderClass:
        def __new__(cls, *args, **kwargs):
            return fake_provider

    return fake_provider, FakeProviderClass


@pytest.mark.asyncio
async def test_csv_ingest_handler_chains_recalc_for_single_det():
    """CSV ingest with both module + det pinned → exactly one
    ``emission_recalc`` chain for that pair, mirroring
    ``factor_ingest_handler``'s single-det shape."""
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        meta={"provider_name": "FakeCSV"},
    )
    _, fake_class = _patch_provider(success=True, extra_data={"inserted": 4})

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_awaited_once()
    chain_kwargs = mock_chain.await_args.kwargs
    assert chain_kwargs["job_type"] == "emission_recalc"
    assert chain_kwargs["module_type_id"] == 5
    assert chain_kwargs["data_entry_type_id"] == 11
    assert chain_kwargs["year"] == 2025
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired


@pytest.mark.asyncio
async def test_csv_ingest_handler_chains_per_det_for_multitype_upload():
    """CSV upload that mixes dets within one module (det NULL) → one
    ``emission_recalc`` chain per det in
    ``MODULE_TYPE_TO_DATA_ENTRY_TYPES`` for the parent's module."""
    from app.models.module_type import (
        MODULE_TYPE_TO_DATA_ENTRY_TYPES,
        ModuleTypeEnum,
    )

    module = ModuleTypeEnum.headcount
    expected_dets = [d.value for d in MODULE_TYPE_TO_DATA_ENTRY_TYPES[module]]

    job = _make_job(
        module_type_id=module.value,
        data_entry_type_id=None,
        year=2025,
        meta={"provider_name": "FakeCSV"},
    )
    _, fake_class = _patch_provider(success=True)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())

    assert mock_chain.await_count == len(expected_dets)
    chained_dets = {c.kwargs["data_entry_type_id"] for c in mock_chain.await_args_list}
    assert chained_dets == set(expected_dets)
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired


@pytest.mark.asyncio
async def test_csv_ingest_handler_skips_fan_out_on_error():
    """ERROR result → no recalc fan-out, parent goes FINISHED+ERROR."""
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        meta={"provider_name": "FakeCSV"},
    )
    _, fake_class = _patch_provider(success=False)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_not_awaited()
    assert meta["result"] == IngestionResult.ERROR
    assert "recalc_jobs_chained" not in meta


@pytest.mark.asyncio
async def test_api_ingest_handler_chains_recalc_on_success():
    """``api_ingest`` (e.g. travel) — single-det shape; one chain."""
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        meta={"provider_name": "FakeAPI"},
    )
    _, fake_class = _patch_provider(success=True)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.api_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_awaited_once()
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired


@pytest.mark.asyncio
async def test_api_ingest_handler_skips_fan_out_on_error():
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        meta={"provider_name": "FakeAPI"},
    )
    _, fake_class = _patch_provider(success=False)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.api_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_not_awaited()
    assert "recalc_jobs_chained" not in meta


@pytest.mark.asyncio
async def test_csv_ingest_handler_raises_when_year_missing():
    """``emission_recalc`` is keyed on ``(data_entry_type_id, year)``
    — a job without ``year`` can't choose a recalc scope.  The
    misconfiguration must surface so the runner records FINISHED+ERROR."""
    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=None,
        meta={"provider_name": "FakeCSV"},
    )
    _, fake_class = _patch_provider(success=True)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock),
    ):
        with pytest.raises(ValueError, match="has no year"):
            await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())


@pytest.mark.asyncio
async def test_csv_ingest_handler_skips_fan_out_when_module_type_id_missing():
    """A data ingest without module_type_id is unexpected (every
    endpoint pins it); log + skip rather than crash the parent's
    FINISHED write.  Parent still finishes SUCCESS."""
    job = _make_job(
        module_type_id=None,
        data_entry_type_id=None,
        year=2025,
        meta={"provider_name": "FakeCSV"},
    )
    _, fake_class = _patch_provider(success=True)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        meta = await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())

    mock_chain.assert_not_awaited()
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired
    assert meta["result"] == IngestionResult.SUCCESS


# ---------------------------------------------------------------------------
# Issue #1219 — dedup on the csv/api fan-out + owned-child count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_csv_ingest_fan_out_passes_dedup_config():
    """Issue #1219 Fix 2: the csv/api recalc fan-out must pass
    ``dedup_config=EMISSION_RECALC_DEDUP`` (it previously did not, so a
    pre-existing active recalc raised an uncaught IntegrityError that
    poisoned the job_session and stranded the parent)."""
    from app.tasks._chain import EMISSION_RECALC_DEDUP

    job = _make_job(
        module_type_id=5,
        data_entry_type_id=11,
        year=2025,
        meta={"provider_name": "FakeCSV"},
    )
    _, fake_class = _patch_provider(success=True)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(ingest_mod, "chain_job", new_callable=AsyncMock) as mock_chain,
    ):
        await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())

    assert mock_chain.await_args.kwargs["dedup_config"] is EMISSION_RECALC_DEDUP


@pytest.mark.asyncio
async def test_csv_ingest_fan_out_counts_only_owned_children():
    """Issue #1219 Fix 2b: a dedup-skipped target (``chain_job``
    returns ``None`` — its recalc is owned by an earlier active
    pipeline) must NOT count toward this pipeline's
    ``recalc_jobs_chained``; otherwise the pipeline-progress contract
    would wait forever for a child that lives under another pipeline.
    """
    from app.models.module_type import (
        MODULE_TYPE_TO_DATA_ENTRY_TYPES,
        ModuleTypeEnum,
    )

    module = ModuleTypeEnum.headcount
    expected_dets = [d.value for d in MODULE_TYPE_TO_DATA_ENTRY_TYPES[module]]
    assert len(expected_dets) >= 2  # multi-det module — fan-out > 1

    job = _make_job(
        module_type_id=module.value,
        data_entry_type_id=None,
        year=2025,
        meta={"provider_name": "FakeCSV"},
    )
    _, fake_class = _patch_provider(success=True)

    # First det: created (returns an id). Remaining dets: dedup-skipped
    # (return None) — already owned by an earlier active pipeline.
    returns = [42] + [None] * (len(expected_dets) - 1)

    with (
        patch.object(
            ingest_mod.ProviderFactory, "get_provider_class", return_value=fake_class
        ),
        patch.object(
            ingest_mod,
            "chain_job",
            new_callable=AsyncMock,
            side_effect=returns,
        ) as mock_chain,
    ):
        meta = await ingest_mod.csv_ingest_handler(job, MagicMock(), MagicMock())

    # All dets attempted, but only the one owned child counts.
    assert mock_chain.await_count == len(expected_dets)
    assert "recalc_jobs_chained" not in meta  # Phase 5B retired
    assert meta["result"] == IngestionResult.SUCCESS
