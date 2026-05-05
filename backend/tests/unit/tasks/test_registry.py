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
    """Ensure each test starts and ends with an empty registry."""
    _reset_registry()
    yield
    _reset_registry()


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
