---
status: proposed
issue: 2397
last_updated: 2026-08-26
title: "Suppress per-chunk ASGI receive/send spans"
summary: "One upload produces 805 spans, one per body chunk, each created and exported on the event loop. The pinned opentelemetry-instrumentation-asgi 0.65b0 supports exclude_spans natively, but only as a keyword argument — and the app is instrumented inside the FastAPI() constructor by opentelemetry-instrument, before our code runs. Proposes an explicit uninstrument/re-instrument at boot, sequenced after #2263 so the win can be measured rather than assumed."
---

# Suppress per-chunk ASGI receive/send spans (#2397)

Split out of [#2049](2049-optimize-pipeline-performance.md) (was D2, promoted
to B6 on 2026-08-26 — its "after A and B land" placement came from a
rationale that never applied to it).

## The finding

A single traced upload produced **805 spans** — one `http receive` per body
chunk — each **created and exported on the event loop**, on the request hot
path. Measured in the v3 trace investigation (trace `a7cfb477…`, 3.037 s,
816 spans total).

Two costs, and they are different:

- **Event-loop time.** Span creation and export are synchronous work on the
  same loop that serves every other request. This is the one that matters.
- **Trace volume.** 805 spans of no analytical value per upload.

## What is already verified

Checked against the actual pinned packages, not assumed:

1. **`opentelemetry-instrumentation-asgi==0.65b0` supports it natively.**
   `OpenTelemetryMiddleware.__init__` takes
   `exclude_spans: list[Literal["receive","send"]] | None` and sets
   `self.exclude_receive_span` / `self.exclude_send_span` from it. **No
   `SpanProcessor` workaround is needed** — #2049 listed this as an open
   question; it is answered.

2. **It is a keyword argument, not an environment variable.** There is no
   `OTEL_*` constant for it anywhere in the instrumentation packages. So it
   cannot be switched on the way every other OTel setting in this app is
   switched on — via the ops-repo overlay.

3. **The app is instrumented inside the `FastAPI(...)` constructor.**
   `backend/Dockerfile:72` runs `opentelemetry-instrument uvicorn
app.main:app`. That calls `FastAPIInstrumentor._instrument()`, which
   monkey-patches `fastapi.FastAPI` with `_InstrumentedFastAPI`, whose
   `__init__` calls `instrument_app(self, **_instrument_kwargs)` — with the
   auto-instrumentation's kwargs, which don't include `exclude_spans`.

   So by the time `app = FastAPI(...)` returns in `main.py`, instrumentation
   is already applied with the wrong settings.

**That mismatch is the entire design problem.** Everything below is a way to
get one keyword argument past a construction step we don't control.

## Options

### A. Uninstrument and re-instrument at boot — **recommended**

Immediately after the app is constructed:

```python
FastAPIInstrumentor.uninstrument_app(app)
FastAPIInstrumentor.instrument_app(app, exclude_spans=["receive", "send"])
```

`uninstrument_app` is public API and clean: it restores
`_original_build_middleware_stack`, rebuilds `app.middleware_stack`, restores
`BackgroundTask.__call__`, and clears
`_is_instrumented_by_opentelemetry`. Verified by reading the pinned source.

- **Cost:** one middleware-stack rebuild at boot. Nothing at request time.
- **Risk:** it must be done _once_, at a known point, and it must fail loudly
  if it throws — a silently un-instrumented app would delete every trace we
  have, which is far worse than 805 spans.

### B. Pre-seed `_InstrumentedFastAPI._instrument_kwargs`

Set the kwarg before constructing the app. **Rejected:** it writes to a
private class attribute of a pinned third-party package. It would break
silently on upgrade — and "silently" is the operative word, since the failure
mode is the spans quietly coming back.

### C. Stop using `opentelemetry-instrument` for FastAPI; instrument manually

**Rejected for now.** It would change how _every_ instrumentation in the app
is configured, not just this one. Far larger blast radius than the problem
justifies.

### D. Drop the spans collector-side

A `filter` processor dropping `* http receive` / `* http send`.

**This does not achieve the goal.** The spans would still be created and
exported on the event loop; only Tempo storage is saved. It addresses the
symptom we can see and not the cost we care about. Worth doing _as well_ if
trace volume becomes a problem, but it is not this fix and must not be
mistaken for it.

## Sequencing — deliberately after #2263

Land `#2263` (`event_loop_lag_seconds`) **first**, let it record a baseline,
then land this and compare.

The reason is honesty about the premise: "805 spans on the event loop are
blocking it" is a _hypothesis_. The 683 ms of unattributed tail time in the
taxonomy traces is a residual, not a measurement, and it could be
serialisation, GC, span export, or queueing behind something else. The lag
probe is the only instrument that discriminates. Shipping this fix first and
declaring victory would be exactly the pattern this plan's own corrections
list keeps catching.

**Expected, and falsifiable:** upload trace span count drops from ~805 to
~11. If `event_loop_lag_seconds` also drops during uploads, the hypothesis
holds and we have a number. **If lag does not move, that is a real result** —
it means the spans were cheap and the 683 ms lives somewhere else, and the
next step is D1's triage rather than more span-suppression.

## What we lose

Per-chunk `http receive` visibility. We have never used it: the upload
investigation used the span _count_ as a symptom, never the individual spans.
The upload's meaningful spans — auth, the S3 round-trips, the root — are
untouched.

If per-chunk timing is ever needed again, it is one boolean away.

## Test

A behavioural test, not a configuration assertion: drive an upload through
the ASGI app with an in-memory span exporter and assert **no span named
`* http receive` is produced**, while the root request span still is.

That pins the actual behaviour, so it survives an instrumentation upgrade
that renames or moves `exclude_spans` — which is the realistic failure mode
given point 2 above.

## Explicitly not in scope

`OTEL_PYTHON_DISABLED_INSTRUMENTATIONS` and `OTEL_TRACES_SAMPLER` are a
separate item (#2049 C2), gated on A1. This changes neither.
