"""Unit tests for the Plan 310-C handler registry.

The registry is a module-level dict, so tests use a fixture that calls
``_reset_registry()`` to keep them independent.
"""

import inspect

import pytest

from app.tasks.registry import (
    _REGISTRY,
    _reset_registry,
    get_handler,
    register,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot the registry, run the test on an empty one, and restore.

    Once Tier 2 wires real handlers via import-time ``@register(...)``,
    those registrations live in the same module-level dict.  An
    unconditional reset in teardown would clobber them and make any
    later test relying on ``get_handler("csv_ingest")`` fail with
    ``No handler registered`` — silently order-dependent.

    Snapshot pattern: capture current state, blank for the test,
    restore unconditionally on teardown so siblings see whatever was
    registered before this test started.
    """
    snapshot = dict(_REGISTRY)
    _reset_registry()
    try:
        yield
    finally:
        _reset_registry()
        _REGISTRY.update(snapshot)


async def _noop_handler(job, job_session, data_session) -> dict:
    return {}


def test_register_decorator_registers_handler():
    @register("foo")
    async def handler(job, job_session, data_session) -> dict:
        return {"ok": True}

    assert get_handler("foo") is handler


def test_register_duplicate_raises():
    register("foo")(_noop_handler)

    with pytest.raises(ValueError, match="already registered"):
        register("foo")(_noop_handler)


def test_get_handler_unknown_raises():
    with pytest.raises(ValueError, match="No handler registered for job_type='bogus'"):
        get_handler("bogus")


def test_register_returns_function_unchanged():
    async def handler(job, job_session, data_session) -> dict:
        return {"answer": 42}

    decorated = register("bar")(handler)

    # Same object back — decorator is a pure side-effect registration.
    assert decorated is handler
    # Signature preserved.
    assert inspect.signature(decorated) == inspect.signature(handler)
    # Still a coroutine function.
    assert inspect.iscoroutinefunction(decorated)


def test_reset_registry_clears():
    register("foo")(_noop_handler)
    register("bar")(_noop_handler)
    assert "foo" in _REGISTRY
    assert "bar" in _REGISTRY

    _reset_registry()

    assert _REGISTRY == {}
    with pytest.raises(ValueError):
        get_handler("foo")
    with pytest.raises(ValueError):
        get_handler("bar")
