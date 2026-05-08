"""Regression: ``DataIngestionProvider.defer_finalize`` suppresses the
provider-side FINISHED state-write so the Plan 310-C runner remains the
single FINISHED authority.

Why this matters (PR #1050 Copilot review):
- ``finished_at`` is auto-stamped on the first transition to FINISHED
  (PR #1026).  If the provider writes FINISHED before the runner's
  ``data_session.commit()``, the duration metric measures provider work
  only — handler post-processing (e.g. ``factor_ingest`` chain fan-out)
  is excluded.
- ``factor_ingest`` chains its emission_recalc children AFTER the
  provider returns.  If the provider already wrote FINISHED, the
  dashboard briefly sees a FINISHED parent with no children attached.
- The runner's preempt-check (re-read row, verify ``locked_by``) only
  protects writes the runner makes.  Provider-side FINISHED writes
  bypass it entirely — a stale-lock sweep + re-claim mid-handler races
  the provider's FINISHED commit.

These tests pin the contract: with ``defer_finalize=True``, the
provider's ``_update_job(state=FINISHED, ...)`` calls land WITHOUT the
state and result fields (status_message + extra_metadata still flow
through for SSE progress).  The default ``defer_finalize=False``
preserves legacy callers that still rely on the provider as the
FINISHED authority (none in production after PR #1050, but safe for
ad-hoc scripts and seed runs).
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_ingestion import (
    IngestionResult,
    IngestionState,
)
from app.services.data_ingestion.base_provider import DataIngestionProvider


class _StubProvider(DataIngestionProvider):
    """Concrete subclass with no-op abstract methods so we can construct
    one in a unit test."""

    async def validate_connection(self) -> bool:
        return True

    async def fetch_data(self, filters):  # type: ignore[override]
        return []

    async def transform_data(self, raw_data):  # type: ignore[override]
        return raw_data

    async def _load_data(self, data):  # type: ignore[override]
        return {"inserted": 0}


def _make_provider_with_mocked_session(
    *, defer_finalize: bool
) -> tuple[_StubProvider, MagicMock]:
    """Build a stub provider wired to a MagicMock job_session whose repo
    we can inspect.  Returns (provider, captured_repo_mock)."""
    job_session = MagicMock()
    job_session.commit = AsyncMock()

    provider = _StubProvider(
        config={"module_type_id": 11, "year": 2025},
        user=None,
        job_session=job_session,
        data_session=MagicMock(),
    )
    provider.job_id = 42
    if defer_finalize:
        provider.defer_finalize = True

    # ``_update_job`` constructs ``DataIngestionRepository(self.job_session)``
    # internally — patch the constructor on the module so we capture the
    # repo instance and its calls.
    import app.services.data_ingestion.base_provider as bp_mod

    repo_mock = MagicMock()
    repo_mock.update_ingestion_job = AsyncMock(return_value=None)
    job_stub = MagicMock()
    job_stub.id = 42
    job_stub.state = IngestionState.RUNNING
    repo_mock.get_job_by_id = AsyncMock(return_value=job_stub)
    repo_mock.mark_job_as_current = AsyncMock(return_value=None)

    bp_mod.DataIngestionRepository = MagicMock(return_value=repo_mock)
    return provider, repo_mock


@pytest.mark.asyncio
async def test_default_provider_writes_finished_state_through():
    """defer_finalize=False (legacy) → provider writes FINISHED + result
    + completed_at as before.  Locks the legacy contract so we don't
    accidentally regress callers that still depend on it."""
    provider, repo_mock = _make_provider_with_mocked_session(defer_finalize=False)

    await provider._update_job(
        status_message="Success",
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        extra_metadata={"message": "done"},
    )

    repo_mock.update_ingestion_job.assert_awaited_once()
    call_kwargs: dict[str, Any] = repo_mock.update_ingestion_job.await_args.kwargs
    assert call_kwargs["state"] == IngestionState.FINISHED
    assert call_kwargs["result"] == IngestionResult.SUCCESS
    assert isinstance(call_kwargs["completed_at"], datetime)
    # mark_job_as_current fires for FINISHED (so the row reflects "current").
    repo_mock.mark_job_as_current.assert_awaited_once()


@pytest.mark.asyncio
async def test_defer_finalize_strips_finished_state_from_write():
    """defer_finalize=True → state, result, and completed_at are stripped
    so the runner remains the single FINISHED authority.  The
    status_message and metadata still land for SSE consumers."""
    provider, repo_mock = _make_provider_with_mocked_session(defer_finalize=True)

    await provider._update_job(
        status_message="Success",
        state=IngestionState.FINISHED,
        result=IngestionResult.SUCCESS,
        extra_metadata={"message": "done"},
    )

    repo_mock.update_ingestion_job.assert_awaited_once()
    call_kwargs: dict[str, Any] = repo_mock.update_ingestion_job.await_args.kwargs
    # The contract: state and result are scrubbed; status_message + metadata
    # still flow through so SSE progress isn't blanked out.
    assert call_kwargs["state"] is None
    assert call_kwargs["result"] is None
    assert call_kwargs["completed_at"] is None
    assert call_kwargs["status_message"] == "Success"
    assert "metadata" in call_kwargs
    # mark_job_as_current must NOT fire — the row hasn't transitioned yet.
    repo_mock.mark_job_as_current.assert_not_awaited()


@pytest.mark.asyncio
async def test_defer_finalize_lets_running_state_through():
    """defer_finalize=True → state=RUNNING (progress updates) still
    write through unchanged.  Only the FINISHED transition is deferred,
    so SSE consumers keep getting ``processing``/``transforming`` ticks."""
    provider, repo_mock = _make_provider_with_mocked_session(defer_finalize=True)

    await provider._update_job(
        status_message="processing",
        state=IngestionState.RUNNING,
        result=None,
        extra_metadata={"message": "Fetching..."},
    )

    repo_mock.update_ingestion_job.assert_awaited_once()
    call_kwargs: dict[str, Any] = repo_mock.update_ingestion_job.await_args.kwargs
    assert call_kwargs["state"] == IngestionState.RUNNING
    assert call_kwargs["result"] is None
    # mark_job_as_current still fires for RUNNING transitions (legacy
    # behavior — frontend uses is_current to know which row to render).
    repo_mock.mark_job_as_current.assert_awaited_once()


@pytest.mark.asyncio
async def test_defer_finalize_strips_finished_error_state_too():
    """defer_finalize=True covers BOTH success and error FINISHED writes.
    Provider error branches ``raise`` after calling ``_update_job(
    state=FINISHED, result=ERROR)``; the runner's exception handler then
    writes the authoritative FINISHED+ERROR with the exception message."""
    provider, repo_mock = _make_provider_with_mocked_session(defer_finalize=True)

    await provider._update_job(
        status_message="failed: boom",
        state=IngestionState.FINISHED,
        result=IngestionResult.ERROR,
        extra_metadata={"error": "boom"},
    )

    call_kwargs: dict[str, Any] = repo_mock.update_ingestion_job.await_args.kwargs
    assert call_kwargs["state"] is None
    assert call_kwargs["result"] is None
    assert call_kwargs["completed_at"] is None


def test_chain_job_no_longer_importable_from_runner():
    """Plan 310-C: ``chain_job`` lives in ``app.tasks._chain``, not
    ``app.tasks.runner``.  The move broke the static import cycle CodeQL
    flagged on PR #1050 (alerts #644/#645/#646: ``ingestion_tasks →
    runner → bootstrap → ingestion_tasks``).  Pin the new location so a
    future refactor that puts chain_job back in runner.py would re-open
    the cycle and fail this test loudly."""
    import app.tasks._chain as chain_mod
    import app.tasks.runner as runner_mod

    assert hasattr(chain_mod, "chain_job")
    assert not hasattr(runner_mod, "chain_job")
