"""Tests for the fire_and_forget background-task helper.

Guards the regression that left recalc jobs stuck in the DB:
``asyncio.create_task(coro)`` returns a Task that asyncio's task tracker
holds with only a weak reference; Python's GC could reap it before the
loop scheduled its first step, so the task never logged anything and
the backing DataIngestionJob row stayed in NOT_STARTED / RUNNING with
no result.

``fire_and_forget`` adds the task to a process-lifetime strong-ref set
so it survives until completion.
"""

import asyncio
import gc

import pytest

from app.tasks._background import _BACKGROUND_TASKS, fire_and_forget


@pytest.mark.asyncio
async def test_fire_and_forget_runs_to_completion_after_caller_returns():
    """The task must finish even after every named reference is dropped.

    Bare ``asyncio.create_task`` would let the Task be garbage-collected
    here; ``fire_and_forget`` keeps it in ``_BACKGROUND_TASKS`` until
    completion.
    """
    finished = asyncio.Event()

    async def _work():
        # Yield once so we model the case where the loop hasn't started
        # the task yet by the time the caller returns.
        await asyncio.sleep(0)
        finished.set()

    def _schedule():
        # Local-scope: the Task object is unreachable as soon as this
        # function returns.  Without strong-ref tracking, GC could
        # collect it before _work even starts.
        fire_and_forget(_work(), name="test-work")

    _schedule()
    gc.collect()  # force the worst-case: try to reap before the task runs

    await asyncio.wait_for(finished.wait(), timeout=1.0)
    assert finished.is_set()


@pytest.mark.asyncio
async def test_fire_and_forget_removes_from_set_when_done():
    """Once the task completes, the strong reference is released so the
    set doesn't grow unboundedly across calls."""
    started_size = len(_BACKGROUND_TASKS)

    async def _work():
        await asyncio.sleep(0)

    task = fire_and_forget(_work())
    assert task in _BACKGROUND_TASKS, "task should be tracked while running"

    await task
    # Done-callbacks may run on a later loop tick; yield to let them fire.
    await asyncio.sleep(0)

    assert task not in _BACKGROUND_TASKS, (
        "task should be removed from the strong-ref set after completion"
    )
    assert len(_BACKGROUND_TASKS) == started_size


@pytest.mark.asyncio
async def test_fire_and_forget_logs_unhandled_exception(caplog):
    """When the coroutine raises, the done-callback logs the error so it
    doesn't disappear silently."""

    async def _boom():
        raise RuntimeError("intentional test failure")

    import logging

    caplog.set_level(logging.ERROR, logger="app.tasks._background")
    task = fire_and_forget(_boom(), name="boom-test")

    # Give the loop a chance to run the task and the done-callback.
    try:
        await task
    except RuntimeError:
        pass
    await asyncio.sleep(0)

    assert any(
        "boom-test" in record.message and "intentional test failure" in record.message
        for record in caplog.records
    ), f"expected error log; got {[r.message for r in caplog.records]!r}"
