---
status: delivered
issue: 2261
last_updated: 2026-08-21
summary: Fix auth-after-body-ingestion on POST /v1/files/temp-upload (a DoS surface) by parsing the multipart body only after the permission check; add a request-content-length span attribute. The double PutObject/HeadObject write is investigated and left alone — it lives in the vendored enacit4r-files package, not this repo.
---

# Upload path fixes: auth ordering, size limit, tracing (#2261)

Follow-up from #1402's trace investigation of `POST /v1/files/temp-upload`
(`docs/src/implementation-plans/1402-trim-down-alerting.md`, tasks T8/T10).

## Investigation findings

**1. S3 client is async, handler is `async def`.** `enacit4r_files.services.s3.S3Service`
(`enacit4r_files/services/s3.py`) uses `aiobotocore.session.get_session()` — a
real async client, not `boto3` inside a threadpool. No event-loop-blocking
issue there.

**2. The double `PutObject`/`HeadObject` is two different writes, not a
redundant duplicate — and it's upstream code, not this repo's.**
`S3FilesStore.write_file()` does two things: (a) uploads the actual file
content (`s3_service.upload_file`), and (b) dumps a JSON sidecar metadata
file via `_dump_file_node()` (`s3_service.upload_local_file`). Each of those
independently calls `_upload_fileobj()`, which does a `put_object` followed
by an unconditional `head_object` to read back `ContentLength`. So the trace's
Put→Head→Put→Head is: content PUT+HEAD, then metadata-sidecar PUT+HEAD — a
real second object, not a retried/duplicated write of the same one.

The post-PUT `HeadObject` _within_ each pair does look redundant on its own
merits: `write_file()` already computes `size = len(content)` in Python
_before_ uploading, and overwrites the HEAD-derived size with it
(`node.size = size`) right after — so the HEAD's return value is discarded.
But this is all inside `enacit4r-files@1.0.0`
(`backend/pyproject.toml`, pulled by git tag from
`github.com/EPFL-ENAC/enacit4r-files`), not code this repo owns. Per the
guardrails ("defer, don't improvise: new dependencies... wait for the
lead"), this is investigated-and-left-alone, not forked or patched here.
Filed conceptually as a note for whoever maintains that package; not
re-pinned or vendored in this PR.

**3. The handler fully buffers each file in memory, no CPU-heavy step
before it's needed.** `S3FilesStore.write_file()` does
`content = await upload_file.read()` to encrypt-then-upload; no hashing or
`pandas.read_csv` runs before the file is actually needed. `FileChecker.check_size`
also does a full `await file.read()` per file to measure length, then seeks
back to 0 — an extra full-content pass, but memory-only, not CPU-bound.

## The real bug: FastAPI parses the whole body before any dependency runs

Confirmed from `fastapi/routing.py` (this version, `fastapi==0.141.1`):
`body = await request.form()` (line ~430) runs **unconditionally, before**
`solve_dependencies()` (line ~481) is even called — for _any_ route whose
dependant tree has a File/Form-typed body parameter, anywhere in its
declared `dependencies=[]` list or function signature. Dependency order in
the decorator/signature has no effect: the full multipart body is read into
`UploadFile`s' `SpooledTemporaryFile`s before FastAPI resolves `Depends(get_current_user)`,
`Depends(file_checker.check_size)`, or anything else. This held even though
`upload_temp_files` already had `dependencies=[Depends(file_checker.check_size)]`
and `FILES_MAX_SIZE_MB` was already a real setting (`backend/app/core/config.py`)
— contrary to the issue's framing, a size limit did already exist, but it
ran too late to stop the buffering it was meant to bound.

## Fix

`backend/app/api/v1/files.py`, `upload_temp_files`:

- Takes the raw `Request` instead of `files: list[UploadFile] = File(...)`,
  and drops the `dependencies=[Depends(file_checker.check_size)]` decorator
  entry (its own `files` parameter also counts as a body field for FastAPI's
  dependant tree, so it had to go too). With no body-typed parameter left
  anywhere in the dependant tree, FastAPI's `body_field` for this route is
  `None`, so `request.form()` is never called automatically — auth runs
  first, unconditionally.
- The permission check (`can_upload`) now runs first; only after it passes
  does the handler call `async with request.form() as form:` and read
  `files`. An unauthenticated or unauthorized caller is rejected before a
  single body byte is read off the wire.
- `_require_upload_files()` narrows `form.getlist("files")`
  (`list[str | UploadFile]`) to real uploads, raising 422 on a plain string
  sent under the same field name — manual parsing skips FastAPI's automatic
  validation, so this has to be explicit. (Narrows against
  `starlette.datastructures.UploadFile`, since `request.form()` returns the
  Starlette base class, not `fastapi.UploadFile`, which is a subclass.)
- `file_checker.check_size(files)` is now called explicitly, right after
  parsing, so the size limit still applies for authenticated callers.
- `openapi_extra={"requestBody": TEMP_UPLOAD_REQUEST_BODY}` reproduces the
  multipart schema FastAPI used to generate automatically (verified against
  a schema dump: identical shape, just inlined instead of via a named
  `components.schemas` ref) — `frontend/src/types/api/openapi.d.ts` and
  `frontend/scripts/openapi.snapshot.json` were hand-updated to match (the
  `Body_upload_temp_files_...` component is gone; the request body type is
  now inline — no consumer referenced that component name).
- `_record_request_content_length()` sets `http.request_content_length` on
  the current span from the `Content-Length` header, best-effort (a
  missing/malformed header just means the attribute is absent, never a
  failed upload).

**Contract change:** a request with no `files` part previously got
FastAPI's automatic `422` (required body field missing). It now reaches the
handler with an empty list and gets `400` ("At least one file must be
provided") from the existing empty-files check. Same outward effect
(rejected, 4xx) with a more specific message; no known caller depends on
the exact status code for this case.

### Left alone

- **A sibling route has the identical hole and is not fixed here.**
  `POST /v1/year-configuration/{year}/upload`
  (`backend/app/api/v1/year_configuration.py:941`) takes
  `file: UploadFile = File(...)` and `category: FileCategory = Form(...)`
  with `Depends(get_current_user)` resolved after them — the same
  `body_field`-forces-`request.form()`-before-`solve_dependencies()`
  ordering bug, and it has **no size limit at all** (no
  `file_checker.check_size` equivalent), which is arguably worse than what
  #2261 reported. Left alone here to keep this PR scoped to the reported
  route; filed as a named follow-up rather than silently left unfixed.
- **A pre-parse Content-Length-based size rejection was considered and
  dropped.** `FILES_MAX_SIZE_MB` is a _per-file_ cap; raw `Content-Length`
  is the whole multipart body (all files + multipart overhead), so a
  legitimate multi-file upload under the per-file cap could trip a
  total-body check. The auth fix already means unauthenticated callers send
  zero bytes; `file_checker.check_size` still bounds authenticated abuse
  per file. Not worth the false-positive risk for a marginal gain.
- **The double PutObject/HeadObject** — investigated in depth (see above),
  confirmed to live in `enacit4r-files`, not forked or patched here.
- **Per-chunk `http receive` span suppression (805 spans/request)** — out of
  scope per the issue, sequenced after pooling work in
  `docs/src/implementation-plans/2049-optimize-pipeline-performance.md` (T8).

## Tests

`backend/tests/unit/v1/test_temp_upload_auth_ordering.py`:

- `test_unauthenticated_upload_never_reads_body` — drives the ASGI app
  directly with a `receive` callable that counts invocations; asserts a 401
  with **zero** calls to `receive()`, proving the body is never pulled off
  the wire for an unauthenticated request.
- `test_temp_upload_route_has_no_body_field` — structural canary: asserts
  the route's `body_field is None`; fails immediately if someone
  reintroduces a `File(...)`/`Form(...)` param or dependency.
- `test_oversized_file_is_rejected_after_auth` — an authenticated caller
  still gets a 400 when `file_checker.check_size` rejects an oversized file,
  proving the manual call didn't silently drop the check.
- `test_upload_rejects_non_file_form_value_for_files_field` — a plain
  string under the `files` field gets 422, not a 500 on `.filename`.

`make ci` (ruff + ty backend, eslint/stylelint + vue-tsc frontend) is green.
Existing `test_files_security.py`, `test_csv_upload_e2e.py`, and
`test_unit_gating_e2e.py` all still pass unchanged.
