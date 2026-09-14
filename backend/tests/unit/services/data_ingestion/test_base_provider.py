"""Unit tests for the shared move helpers on ``DataIngestionProvider``.

Regression coverage for #1559: the tmp->processing move used to be a
one-shot consume with no "already done" branch. When a job crashed/
restarted after the move but before FINISHED, ``sweep_stuck_running_jobs``
reset it to NOT_STARTED and the retry re-attempted the move on a tmp
source the first attempt had already consumed, raising a misleading
"Failed to move file" error even though the data was safe in
``processing/<job_id>/``.
"""

from datetime import UTC, datetime
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
    """No ``data_session`` and no ``self.job`` — these tests exercise the
    move helpers' skip/raise/retry semantics, not the archive folder's
    ``created_at`` disambiguation (covered separately below), so
    ``_archive_folder()`` takes its "can't resolve created_at" fallback
    and every path stays the bare ``<job_id>`` this file already asserts.
    """
    provider = ConcreteProvider({"job_id": job_id}, data_session=None)
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


@pytest.mark.asyncio
async def test_move_to_processing_failure_distinguishes_missing_source():
    """#2220: ``FilesStore.move_file`` (vendored ``enacit4r-files``) swallows
    the real storage exception and returns a bare ``False`` — the raised
    message must still say *why*, distinguishing "source already gone" (a
    concurrent/prior attempt consumed it) from "source present, storage
    error" instead of the old bare "Failed to move file".
    """
    provider = _make_provider()
    provider._files_store = MagicMock()
    # First call: destination doesn't exist (must attempt the move).
    # Second call: diagnosing the failure — source is also gone.
    provider._files_store.file_exists = AsyncMock(side_effect=[False, False])
    provider._files_store.move_file = AsyncMock(return_value=False)

    with pytest.raises(Exception, match="no longer exists"):
        await provider._move_to_processing("tmp/abc/data.csv")


@pytest.mark.asyncio
async def test_move_to_processing_failure_reports_source_still_present():
    provider = _make_provider()
    provider._files_store = MagicMock()
    # Destination missing, then source still present at diagnosis time.
    provider._files_store.file_exists = AsyncMock(side_effect=[False, True])
    provider._files_store.move_file = AsyncMock(return_value=False)

    with pytest.raises(Exception, match="still present"):
        await provider._move_to_processing("tmp/abc/data.csv")


# ======================================================================
# _move_to_processed
# ======================================================================


@pytest.mark.asyncio
async def test_move_to_processed_overwrites_when_destination_already_exists():
    """#2442: ``job_id`` is a bare auto-increment int. On a shared
    environment whose DB gets reset without also clearing file storage,
    an unrelated, months-old job can land on the same id + filename.
    Skipping the move because "something is already there" then serves
    that stale, unrelated file forever instead of what THIS job parsed
    (confirmed live: ``processed/5/headcount_students_factors.csv`` held
    a leftover from 2026-05-18, months before the 2026-09-03 job that
    actually owned id 5). The move must always happen — for a genuine
    same-job retry the content would be identical anyway, so this never
    trades away real idempotency, only the stale-file exposure.
    """
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(return_value=True)
    provider._files_store.move_file = AsyncMock(return_value=True)

    result = await provider._move_to_processed("processing/7/data.csv")

    assert result == "processed/7/data.csv"
    provider._files_store.move_file.assert_awaited_once_with(
        "processing/7/data.csv", "processed/7/data.csv"
    )


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


@pytest.mark.asyncio
async def test_move_to_processed_failure_logs_diagnosis(caplog):
    """#2220: the non-fatal warning should also carry the same
    missing-source-vs-storage-error diagnosis, not a bare message.
    """
    provider = _make_provider()
    provider._files_store = MagicMock()
    provider._files_store.file_exists = AsyncMock(side_effect=[False, False])
    provider._files_store.move_file = AsyncMock(return_value=False)

    with caplog.at_level("WARNING"):
        await provider._move_to_processed("processing/7/data.csv")

    assert "no longer exists" in caplog.text


# ======================================================================
# _archive_folder — #2442 collision-proof naming
# ======================================================================


def test_archive_folder_suffixes_with_created_at_when_job_available():
    """Same-instance path: ``create_job`` sets ``self.job`` directly."""
    provider = _make_provider(job_id=5)
    provider.job = MagicMock(created_at=datetime(2026, 9, 3, 14, 19, 10, 237953, UTC))

    assert provider._archive_folder() == "5-20260903T141910237953"


def test_archive_folder_uses_created_at_from_config_when_job_unset():
    """Background-worker path: a fresh provider is reconstructed from
    ``{**job.__dict__, ...}`` (``ingestion_tasks.py``) — ``self.job`` is
    never set there, but ``created_at`` rides along in ``self.config``.
    """
    provider = ConcreteProvider(
        {"job_id": 9, "created_at": datetime(2026, 9, 3, 14, 19, 10, 0, UTC)},
        data_session=None,
    )
    provider.job_id = 9

    assert provider._archive_folder() == "9-20260903T141910000000"


def test_archive_folder_parses_created_at_given_as_isoformat_string():
    """Defensive: config values aren't guaranteed to stay as live
    ``datetime`` objects (e.g. a round-trip through JSON somewhere).
    """
    provider = ConcreteProvider(
        {"job_id": 9, "created_at": "2026-09-03T14:19:10+00:00"},
        data_session=None,
    )
    provider.job_id = 9

    assert provider._archive_folder() == "9-20260903T141910000000"


def test_archive_folder_falls_back_to_bare_job_id_without_created_at():
    provider = _make_provider(job_id=5)
    provider.job = MagicMock(created_at=None)

    assert provider._archive_folder() == "5"


def test_archive_folder_distinguishes_same_id_across_db_epochs():
    """The exact bug (#2442): two unrelated jobs landed on the same
    auto-increment id (5) months apart, across a DB reset that never
    cleared file storage. Naming by id alone made them collide;
    ``created_at`` never does.
    """
    old_job = _make_provider(job_id=5)
    old_job.job = MagicMock(created_at=datetime(2026, 5, 18, 15, 39, 0, 0, UTC))

    new_job = _make_provider(job_id=5)
    new_job.job = MagicMock(created_at=datetime(2026, 9, 3, 14, 19, 10, 237953, UTC))

    assert old_job._archive_folder() != new_job._archive_folder()
