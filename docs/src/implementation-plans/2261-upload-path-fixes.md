---
status: delivered
issue: 2261
summary: Close auth-after-body-ingestion (a DoS surface) on both upload routes — POST /v1/files/temp-upload and POST /v1/year-configuration/{year}/upload — with an AuthFirstRoute custom APIRoute that authenticates and bounds Content-Length before FastAPI reads the body, letting the endpoints keep ordinary File/Form signatures. Adds the per-file size cap the year-configuration route never had. The double PutObject/HeadObject write lives in the vendored enacit4r-files package and is filed upstream, not patched here.
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
Not filed as an issue against `enacit4r-files` — noted here for whoever
next touches that package's upload path; not re-pinned or vendored in
this PR.

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

The workaround lives in **one** place: `AuthFirstRoute`
(`backend/app/api/auth_first_route.py`), a custom `APIRoute`. A route's
handler runs _before_ FastAPI parses the body, so the two checks that don't
need the body happen there, and every endpoint keeps ordinary
`File(...)`/`Form(...)` signatures with an automatically generated OpenAPI
schema.

An earlier version of this PR did it per-route instead — raw `Request`,
manual `request.form()`, re-narrowing the parts FastAPI would have
validated, and a hand-written `openapi_extra` to replace the schema FastAPI
no longer generated, plus hand-patched `openapi.snapshot.json` and
`openapi.d.ts`. It worked, but it was ~120 lines of machinery per route to
work around one framework behaviour, and every future upload endpoint would
have had to repeat it. Replaced. `files.py` and `year_configuration.py` are
now identical to their pre-fix versions apart from the router line and one
size check, and **the generated frontend client needs no patching at all**.

`AuthFirstRoute` does two things:

- **`_reject_unauthenticated`** — requires a correctly-signed, unexpired JWT
  cookie. Deliberately _not_ a second implementation of authentication: it
  proves only that the caller holds a valid token, so there is no copy of
  the auth rules to drift. The endpoint's own `Depends(get_current_user)`
  still enforces the access-token contract and loads the user, and its
  permission check still decides what that user may do.
- **`_reject_oversized`** — refuses a body whose declared `Content-Length`
  exceeds a ceiling, on the header alone, before a byte is read. This is a
  _coarse pre-filter_, not the enforcement point: `FILES_MAX_SIZE_MB` is a
  **per-file** cap while `Content-Length` covers the whole multipart body,
  so a legitimate multi-file upload can exceed the per-file cap in total.
  The exact per-file `check_size` still runs after parsing. Neither check
  alone is both safe and correct. Best-effort by nature — a missing or
  malformed header (or a chunked upload, which has none) means the check
  doesn't apply, never a failed upload. It also sets
  `http.request_content_length` on the span, so slow-client and large-file
  can be told apart in traces.

Applied **router-wide** to `files.py` and `year_configuration.py`, after
verifying that all four routes on the first and all six on the second
already require `get_current_user` — the class makes the auth cookie
mandatory for every route it covers, so that check is a precondition, not a
formality.

**Trade-off, stated plainly.** Authentication now gates body ingestion;
authorization still gates the operation. An authenticated caller who lacks
permission has their body read before the 403, where the earlier per-route
version rejected them first. That is the standard boundary, the caller is
identified and auditable, and the transfer is bounded by the Content-Length
ceiling — whereas _unauthenticated_ callers, the actual reported DoS
surface, now send zero bytes.

### The sibling route, fixed here too

`POST /v1/year-configuration/{year}/upload`
(`backend/app/api/v1/year_configuration.py`) had the identical hole:
`file: UploadFile = File(...)` and `category: FileCategory = Form(...)` with
`Depends(get_current_user)` resolved after them — the same
`body_field`-forces-`request.form()`-before-`solve_dependencies()` ordering
bug — and it had **no size limit at all**, which is worse than what #2261
originally reported.

This was first scoped out and filed as
[#2267](https://github.com/EPFL-ENAC/co2-calculator/issues/2267). That was
the wrong call: shipping the fix for one route while knowingly leaving an
identical, less-protected hole open in the same release is exactly the
"patch the path the ticket names, leave the siblings broken" failure the
guardrails warn about. Both routes are fixed in this PR; #2267 closes with
it.

Because the fix is a route class, this route needed **no restructuring at
all** — it keeps its `File(...)`/`Form(...)` signature, and `FileCategory`
stays validated by FastAPI rather than hand-parsed against `get_args(...)`.
The whole change is the router line plus one added line, the exact per-file
cap this route never had:

```python
await file_checker.check_size([file])
```

**The size cap is a behaviour change, not just a hardening.** Uploads to
this route larger than `FILES_MAX_SIZE_MB` now get a 400 where they
previously succeeded. That cap already governs every other upload path, so
this route was the outlier.

### Left alone, and one thing reversed

- **The pre-parse Content-Length rejection was first dropped, then built.**
  The original objection stands on its own terms — `FILES_MAX_SIZE_MB` is a
  per-file cap and `Content-Length` is the whole multipart body, so a
  legitimate multi-file upload under the per-file cap would trip a naive
  total-body check. The mistake was concluding "therefore no early check".
  A _generous_ ceiling (`MAX_UPLOAD_FILES × FILES_MAX_SIZE_MB`) has no
  false-positive risk and still refuses an absurd body on the header alone;
  the precise per-file check runs afterwards as before. Coarse guard early,
  exact guard late.
- **The double PutObject/HeadObject** — investigated in depth (above),
  confirmed to live in `enacit4r-files`, not forked or patched here. Filed
  upstream as
  [enacit4r-files#25](https://github.com/EPFL-ENAC/enacit4r-files/issues/25),
  alongside
  [#24](https://github.com/EPFL-ENAC/enacit4r-files/issues/24) for the
  swallowed exceptions that made #2220 hard to diagnose.
- **Per-chunk `http receive` span suppression (805 spans/request)** — still
  out of scope _here_, but no longer sequenced behind the pooling work. It
  has no dependency on it, and 805 spans created and exported on the event
  loop sit directly on the upload hot path. Tracked in
  `2049-optimize-pipeline-performance.md`.

## Tests

`backend/tests/unit/v1/test_temp_upload_auth_ordering.py` and
`test_year_configuration_upload_auth_ordering.py` (10 tests, both routes).

The authenticated tests mint a **real signed token** rather than relying on
`app.dependency_overrides`: a route class sits outside dependency
injection, so overriding `get_current_user` does not satisfy the gate and
such a test would prove nothing about it.

- `test_unauthenticated_upload_never_reads_body` (both routes) — drives the
  ASGI app directly with a `receive` callable that counts invocations, and
  asserts a 401 with **zero** calls. `receive` is the only way the server
  can pull the payload off the wire, so this is the load-bearing assertion
  of the whole PR. It is unchanged from the first implementation and passes
  against the route-class one, which is what verified that a route handler
  really does run before body parsing.
- `test_oversized_content_length_rejected_before_body_is_read` — a valid
  token and an oversized declared length: 413 with **zero** `receive`
  calls.
- `test_upload_routes_use_auth_first_route` /
  `test_reduction_objective_upload_uses_auth_first_route` — structural
  canaries. Dropping `route_class` silently restores the original bug while
  every happy-path test keeps passing, so the wiring itself is asserted.
- `test_openapi_documents_the_multipart_body` — pins that the schema is
  still generated and the frontend client generator still sees both parts.
- `test_oversized_file_is_rejected_after_auth` (both routes) — the exact
  per-file cap still applies after parsing.
- `test_upload_rejects_non_file_form_value_for_files_field`,
  `test_upload_rejects_unknown_category` — FastAPI's own validation, which
  keeping the `File(...)`/`Form(...)` signatures gives back for free.

ruff, ty and vue-tsc are green. No frontend files change, so the generated
client and its snapshot are untouched.
