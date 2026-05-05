"""Strong-reference helper for fire-and-forget asyncio background tasks.

asyncio's task tracker holds **weak** references to running tasks (since
Python 3.11): a Task with no other strong reference can be garbage-
collected mid-execution, even before its first await.  In practice we've
seen recalc jobs created via ``asyncio.create_task(coro)`` never run at
all — the task object goes out of scope the moment the calling function
returns, GC reaps it before the loop schedules its first step, and the
backing DataIngestionJob row stays in NOT_STARTED (or stuck in RUNNING
if it just barely cleared claim_job before being collected).

Per the asyncio docs: "Save a reference to the result of this function,
to avoid a task disappearing mid-execution."  This module does that
with a process-lifetime set; the done-callback removes the reference
so completed tasks don't leak.

Use ``fire_and_forget(coroutine)`` instead of ``asyncio.create_task``
for any background work whose return value the caller doesn't await.
"""

import asyncio
from typing import Coroutine

from app.core.logging import get_logger

logger = get_logger(__name__)


_BACKGROUND_TASKS: set[asyncio.Task] = set()


def fire_and_forget(coro: Coroutine, *, name: str | None = None) -> asyncio.Task:
    """Schedule ``coro`` and hold a strong reference until it finishes.

    Returns the Task so callers may add additional callbacks if they need
    to.  Errors raised inside the coroutine are logged via the done-
    callback so they don't disappear into a swallowed exception.
    """
    task = asyncio.create_task(coro, name=name)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_on_done)
    return task


def _on_done(task: asyncio.Task) -> None:
    _BACKGROUND_TASKS.discard(task)
    if task.cancelled():
        # Loud on purpose: a silently-cancelled fire-and-forget task is
        # indistinguishable from "task never ran" in the logs, which makes
        # stuck DataIngestionJob rows nearly impossible to diagnose.  If
        # cancellations become routine for some path, route that path
        # through its own helper instead of quieting this branch.
        logger.warning(f"fire_and_forget task {task.get_name()!r} was cancelled")
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            f"fire_and_forget task {task.get_name()!r} failed: {exc}",
            exc_info=exc,
        )
