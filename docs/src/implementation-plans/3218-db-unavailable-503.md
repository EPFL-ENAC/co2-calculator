---
status: delivered
issue: 3218
last_updated: 2026-11-10
summary: Exception handlers were dropped in prod by the OTel stack rebuild; DB outages now answer 503 + Retry-After and the frontend shows a notice instead of a GlitchTip error.
---

# 3218 — Return HTTP 503 when the database is not available

## Cause

On 2026-11-10 at 01:44 the prod `PATCH /v1/carbon-reports/1070/modules/1/status`
answered 500. The trace shows the pool pre-ping failing (`SSL error:
unexpected eof`), then the reconnect refused by PgBouncer with
`server_login_retry`. `db_unavailable_handler` (since v1.4.19, #2049)
classifies that error as an outage, but it never ran.

Under `opentelemetry-instrument`, `exclude_per_chunk_asgi_spans()` (#2397)
builds `app.middleware_stack` mid-module. Starlette copies
`app.exception_handlers` into `ExceptionMiddleware` at build time, so every
`add_exception_handler()` call placed after it was ignored in prod: DB
outages and permission denials (403) both answered 500. Locally and in
pytest the app is not instrumented, so the handlers worked there.

## Fix

- `backend/app/main.py`: handlers are passed to `FastAPI(exception_handlers=...)`,
  so they exist before any stack is built, whatever the order below.
- `db_unavailable_handler`: `503`, `Retry-After: 30`,
  `{"detail": "database_unavailable"}`, one `event=db_unavailable` log line
  without traceback. Classification is unchanged (connect failure,
  invalidated connection, `explain_db_wait`); statement timeouts and other
  errors stay 500.
- `frontend/src/api/http.ts`: a 503 with `database_unavailable` shows the
  translated "service unavailable, not saved, try again" notice and sends
  no GlitchTip event. The caller still gets the `HTTPError`.

## Tests

- `test_handlers_survive_opentelemetry_instrument`: re-imports `app.main`
  under the FastAPI instrumentor and reads the handlers from the built
  stack. Fails without the fix.
- `test_db_unavailable_is_503`: adds the incident's `server_login_retry`
  connect error; asserts header, detail and log shape.
- `frontend/tests/unit/database-unavailable-notice.spec.ts`: the notice
  shows, the raw code does not.

## Not done

- No automatic retry or Retry button: the ky client keeps `retry: 0`.
  A Retry button belongs to each form, which owns the request to resend.
- No PgBouncer in docker-compose; the unit tests feed the bouncer's real
  error text instead.
