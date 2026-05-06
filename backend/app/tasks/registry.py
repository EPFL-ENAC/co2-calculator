"""Handler registry for Plan 310-C unified job dispatch.

Plan 310-C unifies background-job dispatch under a single ``run_job(job_id)``
runner. Each ``DataIngestionJob.job_type`` maps to exactly one handler
coroutine; this module owns that mapping.

Handlers are registered with the :func:`register` decorator at import time
(typically next to the handler definition in ``app/tasks/*_tasks.py``).
The runner (landing in a follow-up tier) looks up the handler via
:func:`get_handler` and invokes it with a freshly opened pair of sessions:

    handler(job, job_session, data_session) -> dict

The returned ``dict`` becomes ``job.meta`` on success.

This module is greenfield in this PR: no handlers are registered yet. The
registry has no callers until Tier 2 wires up the runner and existing tasks.
"""

import inspect
from typing import Awaitable, Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_ingestion import DataIngestionJob

# Handler signature:
#   handler(job, job_session, data_session) -> dict (becomes job.meta on success)
HandlerFn = Callable[
    [DataIngestionJob, AsyncSession, AsyncSession],
    Awaitable[dict],
]

_REGISTRY: dict[str, HandlerFn] = {}

# Required positional parameter count for the handler contract:
#   (job, job_session, data_session) -> Awaitable[dict]
_HANDLER_REQUIRED_ARITY = 3


def register(job_type: str):
    """Decorator to register a handler for a ``job_type``.

    Raises :class:`ValueError` if:

    - ``job_type`` is already registered (accidental double-import or naming
      collision fails loudly at import time rather than silently shadowing).
    - The decorated function is not a coroutine function (the runner does
      ``await handler(...)``; a sync function would only fail at first
      dispatch, far from where the bug was introduced).
    - The signature does not accept the required ``(job, job_session,
      data_session)`` arity. We accept ``*args``-style handlers as long as
      the callable can take 3 positional arguments.
    """

    def decorator(fn: HandlerFn) -> HandlerFn:
        if job_type in _REGISTRY:
            raise ValueError(f"job_type {job_type!r} already registered")
        if not inspect.iscoroutinefunction(fn):
            raise ValueError(
                f"handler for job_type {job_type!r} must be `async def`; got {fn!r}"
            )
        sig = inspect.signature(fn)
        params = list(sig.parameters.values())
        positional = [
            p
            for p in params
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
        ]
        has_var = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in positional)
        # Required positionals are those without defaults (excluding *args).
        required = [
            p
            for p in positional
            if p.kind != inspect.Parameter.VAR_POSITIONAL
            and p.default is inspect.Parameter.empty
        ]
        accepts_arity = (has_var or len(positional) >= _HANDLER_REQUIRED_ARITY) and len(
            required
        ) <= _HANDLER_REQUIRED_ARITY
        if not accepts_arity:
            raise ValueError(
                f"handler for job_type {job_type!r} must accept "
                f"(job, job_session, data_session); got signature {sig}"
            )
        _REGISTRY[job_type] = fn
        return fn

    return decorator


def get_handler(job_type: str) -> HandlerFn:
    """Return the handler registered for ``job_type``.

    Raises :class:`ValueError` if no handler has been registered. The runner
    is expected to surface this as a job failure rather than crash.
    """
    handler = _REGISTRY.get(job_type)
    if handler is None:
        raise ValueError(f"No handler registered for job_type={job_type!r}")
    return handler


# --- test-only helper ---------------------------------------------------------
# Production code must not call this; the registry is process-lifetime state
# populated by import-time decorators.
def _reset_registry() -> None:
    """Test helper — clears the registry between tests so tests can re-register."""
    _REGISTRY.clear()
