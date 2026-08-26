"""#2397 -- ``exclude_per_chunk_asgi_spans`` (backend/app/main.py).

A single traced upload produced 805 ``http receive`` spans, one per body
chunk, created and exported on the event loop. The pinned
``opentelemetry-instrumentation-asgi`` supports dropping them
(``exclude_spans``), but only as a keyword argument with no ``OTEL_*`` env
var, and ``opentelemetry-instrument`` (backend/Dockerfile) already
instrumented the app inside its own ``FastAPI()`` constructor call before
this module's code runs. Re-instrumenting is the only way to apply it.

This is a real regression test, not a configuration assertion, because the
mechanism has two independent silent-failure modes that were only found by
running it against the real pinned packages, not by reading their source:

- Calling ``FastAPIInstrumentor.uninstrument_app`` / ``instrument_app``
  *before* the app's own ``add_middleware(...)`` calls crashes the app at
  boot (``uninstrument_app`` eagerly rebuilds and assigns
  ``app.middleware_stack``, and Starlette refuses ``add_middleware`` once
  that is set).
- Doing the dance *after* ``add_middleware(...)`` but without the final
  ``app.middleware_stack = app.build_middleware_stack()`` rebuild does not
  crash and does not error -- it silently drops **all** OTel spans, not
  just receive/send, because ``instrument_app`` only re-patches the
  ``build_middleware_stack`` method, never the already-built stack.

The one test below pins all three properties that must hold at once:
spans are still produced (catches the missing final rebuild), receive/send
spans are specifically absent (catches a dropped/wrong ``exclude_spans``),
and a caller-registered middleware still runs (catches a broken stack that
happens to still emit request spans without the app being fully wired).
"""

from contextlib import contextmanager

import fastapi
import opentelemetry.trace as trace_api
from fastapi import File, UploadFile
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.util._once import Once
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.testclient import TestClient

from app.main import exclude_per_chunk_asgi_spans


@contextmanager
def isolated_global_tracer_provider(provider: TracerProvider):
    """Make ``provider`` the process-global tracer provider for the
    duration of the block, then restore whatever was there before.

    ``trace.set_tracer_provider`` is a genuine "first call wins" API --
    calling it a second time in-process is a silent no-op with a logged
    warning. ``exclude_per_chunk_asgi_spans`` deliberately never passes an
    explicit ``tracer_provider`` (matching how the original
    opentelemetry-instrument auto-instrumentation resolves its tracer too),
    so testing its real behaviour needs the *global* provider swapped, not
    a parameter. Resetting the module-private guard and restoring it
    afterward is the same pattern the OTel SDK's own test helpers use --
    it must not leak a live provider into every other test in this process.
    """
    original_provider = trace_api._TRACER_PROVIDER
    original_once = trace_api._TRACER_PROVIDER_SET_ONCE
    trace_api._TRACER_PROVIDER = None
    trace_api._TRACER_PROVIDER_SET_ONCE = Once()
    try:
        trace_api.set_tracer_provider(provider)
        yield
    finally:
        trace_api._TRACER_PROVIDER = original_provider
        trace_api._TRACER_PROVIDER_SET_ONCE = original_once


def test_noop_when_not_running_under_opentelemetry_instrument():
    """A plain, non-monkeypatched FastAPI app (every local `uv run
    uvicorn`/pytest run) has no ``_is_instrumented_by_opentelemetry``
    attribute at all -- this must not raise or otherwise touch the app.
    """
    app = fastapi.FastAPI()
    before = app.middleware_stack
    exclude_per_chunk_asgi_spans(app)
    assert app.middleware_stack is before


def test_receive_send_spans_dropped_others_kept_middleware_intact():
    """Simulates opentelemetry-instrument's global monkeypatch of
    ``fastapi.FastAPI``, builds an app the way ``main.py`` does (construct,
    then ``add_middleware``), calls the function under test, then drives a
    multi-KB upload through it -- the shape that produced 805 spans in
    production.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # No tracer_provider passed to either instrument() call below, on
    # purpose: exclude_per_chunk_asgi_spans never passes one either, so this
    # only proves anything if both calls resolve the tracer the same way
    # main.py's real call does -- via the ambient global provider.
    with isolated_global_tracer_provider(provider):
        instrumentor = FastAPIInstrumentor()
        instrumentor.instrument()
        try:
            app = fastapi.FastAPI()

            @app.post("/upload")
            async def upload(file: UploadFile = File(...)):
                content = await file.read()
                return {"size": len(content)}

            middleware_ran = {"value": False}

            class MarkerMiddleware(BaseHTTPMiddleware):
                async def dispatch(self, request, call_next):
                    middleware_ran["value"] = True
                    return await call_next(request)

            # Mirrors main.py: add_middleware() calls happen before the
            # function under test runs -- that order is exactly what it
            # must tolerate.
            app.add_middleware(MarkerMiddleware)

            exclude_per_chunk_asgi_spans(app)

            with TestClient(app) as client:
                body = b"x" * (64 * 1024)
                response = client.post(
                    "/upload",
                    files={"file": ("f.bin", body, "application/octet-stream")},
                )
            assert response.status_code == 200
            assert response.json() == {"size": len(body)}
            assert middleware_ran["value"], (
                "user middleware registered before the re-instrumentation "
                "dance must still run afterward"
            )

            names = [span.name for span in exporter.get_finished_spans()]
            assert names, (
                "no spans were produced at all -- the middleware_stack "
                "rebuild after instrument_app is missing, so OTel "
                "instrumentation was silently dropped entirely, not just "
                "receive/send spans"
            )
            assert not any("http receive" in n or "http send" in n for n in names), (
                f"per-chunk receive/send spans were not excluded: {names}"
            )
        finally:
            instrumentor.uninstrument()
