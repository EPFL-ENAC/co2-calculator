"""Unit tests for the shared move helpers on ``DataIngestionProvider``.

Regression coverage for #1559: the tmp->processing move used to be a
one-shot consume with no "already done" branch. When a job crashed/
restarted after the move but before FINISHED, ``sweep_stuck_running_jobs``
reset it to NOT_STARTED and the retry re-attempted the move on a tmp
source the first attempt had already consumed, raising a misleading
"Failed to move file" error even though the data was safe in
``processing/<job_id>/``.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.data_ingestion.base_provider import DataIngestionProvider


class ConcreteProvider(DataIngestionProvider):
    """Minimal concrete subclass — only exists to exercise the base class's
    move helpers, which are the thing under test here.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._files_store: Any = None

    @property
    def files_store(self) -> Any:
        return self._files_store

    async def validate_connection(self) -> bool:
        return True

    async def fetch_data(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def transform_data(
        self, raw_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return raw_data

    async def _load_data(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        return {"inserted": 0, "skipped": 0, "errors": 0}


def _make_provider(job_id: int = 7) -> ConcreteProvider:
    provider = ConcreteProvider({"job_id": job_id}, data_session=MagicMock())
    provider.job_id = job_id
    return provider


# ======================================================================
# _move_to_processing
# ======================================================================


@pytest.mark.asyncio
async def test_move_to_processing_skips_when_destination_already_exists():
    """Retry after a prior successful move: destination present, tmp/
    source already consumed. Must skip the move, not fail.
    """
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=True)
    provider._files_store.move_file = AsyncMock(
        side_effect=AssertionError(
            "move_file must not be called when destination exists"
        )
    )

    result = await provider._move_to_processing("tmp/abc/data.csv")

    assert result == "processing/7/data.csv"
    provider._files_store.move_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_move_to_processing_moves_when_destination_missing():
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store.move_file = AsyncMock(return_value=True)

    result = await provider._move_to_processing("tmp/abc/data.csv")

    assert result == "processing/7/data.csv"
    provider._files_store.move_file.assert_awaited_once_with(
        "tmp/abc/data.csv", "processing/7/data.csv"
    )


@pytest.mark.asyncio
async def test_move_to_processing_raises_on_genuine_move_failure():
    """A real move failure (permissions, disk, or a genuinely missing
    source) with no destination present is still fatal — the idempotency
    check must not swallow every failure, only the already-done case.
    """
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store.move_file = AsyncMock(return_value=False)

    with pytest.raises(Exception, match="Failed to move file"):
        await provider._move_to_processing("tmp/abc/data.csv")


# ======================================================================
# _move_to_processed
# ======================================================================


@pytest.mark.asyncio
async def test_move_to_processed_skips_when_destination_already_exists():
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=True)
    provider._files_store.move_file = AsyncMock(
        side_effect=AssertionError(
            "move_file must not be called when destination exists"
        )
    )

    result = await provider._move_to_processed("processing/7/data.csv")

    assert result == "processed/7/data.csv"
    provider._files_store.move_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_move_to_processed_moves_when_destination_missing():
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store.move_file = AsyncMock(return_value=True)

    result = await provider._move_to_processed("processing/7/data.csv")

    assert result == "processed/7/data.csv"


@pytest.mark.asyncio
async def test_move_to_processed_failure_is_non_fatal():
    """Unlike tmp->processing, a processing->processed failure must not
    raise — the ingested data is already committed; only archival
    bookkeeping is at stake. Falls back to the un-moved path.
    """
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=False)
    provider._files_store.move_file = AsyncMock(return_value=False)

    result = await provider._move_to_processed("processing/7/data.csv")

    assert result == "processing/7/data.csv"
