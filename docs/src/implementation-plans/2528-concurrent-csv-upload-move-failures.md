---
status: in-progress
issue: 2528
last_updated: 2026-08-30
summary: "Concurrent CSV uploads fail on the tmp/ to processing/ move
  (56% at 20 parallel uploaders on S3, 0.8% on the local store).
  The move is an unretried copy_object+delete_object; any transient S3
  fault kills the job permanently. Plan: bounded idempotent retry at the
  single choke point, one shared S3 client per process with a sized pool,
  and botocore standard retry mode via the chart."
---

# Concurrent CSV upload move failures (#2528)

**Goal:** an upload flow at 20 parallel uploaders against the S3 file
store fails no more often than against the local store (0.8%), and no
`Error moving file` reaches a user.

Found by the #2295 load suite (PR #2526). Read
[`2295-load-tests-locust.md`](./2295-load-tests-locust.md) for the
harness and [`1559-ingestion-idempotent-tmp-to-processing-move.md`](./1559-ingestion-idempotent-tmp-to-processing-move.md)
for the existing idempotency guard this plan builds on.

## The path, traced

One CSV upload flow crosses these:

| Step | Code | S3 calls |
| ---- | ---- | -------- |
| `POST /v1/files/temp-upload` | `backend/app/api/v1/files.py` → `files_store.write_file` into `tmp/<ts>/` | put_object + metadata sidecar |
| `POST /v1/sync/dispatch` | job row, then `run_job` under the `MAX_CONCURRENT_JOBS=4` semaphore | — |
| move | `DataIngestionProvider._move_to_processing` (`backend/app/services/data_ingestion/base_provider.py`) | head_object, **copy_object**, delete_object, + sidecar |
| read | `files_store.get_file(processing_path)` | get_object |
| archive | `_move_to_processed` | head_object, copy_object, delete_object, + sidecar |

The move itself lands in `enacit4r-files` 1.2.0 (`enacit4r_files/services/s3.py`),
pinned by tag in `backend/pyproject.toml`.

## Evidence: what is proven from the code

1. **The reported message is the dependency's, character for character.**
   `S3FilesStore.move_file` wraps its body in `try/except Exception` and
   does `logging.exception(f"Error moving file from {source_path} to
   {destination_path}")`, then
   `raise S3Error(f"Error moving file from … to …: {e}") from e`.
   So the failure is an **exception raised inside `S3Service.move_file`**
   — i.e. in `copy_object` or `delete_object`. It is not a falsy return,
   and it is not the metadata sidecar (that is caught separately and only
   ever logs a warning).

2. **The move is copy + delete, not a rename.** `S3Service.move_file`
   calls `copy_file()` (`copy_object`) and, only if that returned
   non-`False`, `delete_file()` (`delete_object`) — two network round
   trips, non-atomic. `LocalFilesStore.move_file` is `shutil.move`, a
   same-filesystem rename with no network at all. That asymmetry is the
   whole 56% vs 0.8% gap.

3. **The app never retries the move.** `_move_to_processing` calls it
   once. The exception propagates through `_setup_and_validate` to
   `process_csv_in_batches`, whose handler writes
   `state=FINISHED, result=ERROR` itself. Because the provider makes the
   job terminal, the runner's `attempts < max_attempts` retry never
   engages — which is exactly why **every failed job shows
   `attempts = 1`**. That is not evidence against a retry bug; it is
   evidence there is no retry at all.

4. **The dependency's two stores now disagree, and the app follows
   neither.** `_move_to_processing` reads
   `if not await self.files_store.move_file(...)` and builds a message
   from `_diagnose_move_failure` on a falsy return. In the pinned 1.2.0:

   | Store | On failure |
   | ----- | ---------- |
   | `S3FilesStore.move_file` | **raises `S3Error`**, original chained (their #24) |
   | `LocalFilesStore.move_file` | still `except Exception: logging.error(…); return False` |

   So the falsy-return branch and `_diagnose_move_failure` are **dead
   code on S3** — confirmed by the issue reporting the dependency's
   `S3Error` wording rather than the app's own "Failed to move file from
   …" — while remaining the **only** failure signal on local. A fix that
   only catches, or only tests the return value, is broken on one of the
   two stores. **Both must be handled.**

   This is the wider finding behind #2528: the tag bump to 1.2.0 changed
   the S3 contract from return-`False` to raise, and nothing on the app
   side was updated to match — not the code, not the tests, and not the
   comments. `base_provider._diagnose_move_failure`'s docstring and
   `tests/unit/services/data_ingestion/test_base_provider.py:111` both
   still describe the dependency as swallowing the exception and
   returning a bare `False` (#2220), which is now true of only the local
   store. The missing retry is one symptom of that drift.

5. **One S3 client per job, never closed.** `make_files_store()` builds a
   fresh `S3Service`; `base_csv_provider`, `base_factor_csv_provider`,
   `base_reduction_objective_csv_provider` and
   `csv_providers/reference_data` each call it lazily **per provider
   instance**, so every ingestion job constructs its own client. 1.2.0
   keeps that client alive for the life of the `S3Service` (its docstring
   says "Call close() on application shutdown") and nothing in the app
   ever calls `close()`. Every finished job leaves an aiobotocore client
   and its aiohttp connector behind.

6. **Pool and retries are at their defaults.** `S3Service.__init__` takes
   `max_pool_connections: int = 10` and `make_files_store()` does not
   pass it. Its `Config` sets no `retries=`, and neither the repo nor the
   chart sets `AWS_RETRY_MODE` / `AWS_MAX_ATTEMPTS`, so botocore's
   `legacy` mode applies (pinned: aiobotocore 2.12.4, botocore 1.34.106).

7. **The user cannot recover without re-uploading.** `copy_object`
   failing means `delete_object` never runs, so the CSV is still in
   `tmp/<ts>/` — no data loss, but nothing GCs `tmp/`.
   `POST /v1/sync/jobs/{id}/recover` only accepts stale **RUNNING** rows
   (`stale_running_clause`), so a job that went FINISHED/ERROR here is
   terminal. Re-upload + re-dispatch is the only path, and the orphan
   stays.

## Root-cause hypotheses, ranked

**H1 — the move has no retry, so any transient S3 fault is fatal.**
*Proven* (fact 3), and sufficient on its own to explain the shape: fails
at 5 uploaders, worse at 20, near-zero on a store with no network. This
is the one certain defect, and it is worth fixing whatever turns out to
be underneath it.

**H2 — client accumulation from never calling `close()`.**
*Mechanism proven* (fact 5), *magnitude unproven*. At
`MAX_CONCURRENT_JOBS=4` × 2–3 replicas and ~18 flows/min the
accumulation is bounded, and aiohttp closes transports on GC — so this
fits a failure rate that **climbs over the run** better than a flat 56%.
If the 20-user failures were spread evenly rather than rising, H2 is not
the driver.

**H3 — endpoint-side throttling or connection caps on the S3-compatible
store.** *Suspected.* Failure rate scaling with concurrency and the ~70×
local/S3 gap both point at the network path. Whether it is 503/`SlowDown`
(which botocore `standard` retry mode absorbs by itself) or
`ClientConnectorError` / `ConnectTimeoutError` (which needs pool sizing)
cannot be decided from the code.

**H4 — `tmp/` path collision.** *Weak.* `folder_name` is
`str(datetime.now(UTC).timestamp()).replace(".", "")`, and `CsvUploadUser`
picks from a handful of fixed filenames — two uploads in the same
microsecond with the same name would collide. At ~182 flows the odds are
tiny, and the symptom would be a few "source no longer exists", not 56%.

**H5 — a retry re-moving an already-moved file.** *Falsified* in the
issue by `attempts = 1`, and independently by #1559's destination-exists
check already at the top of `_move_to_processing`.

### The one measurement that reorders this list

`logging.exception` wrote a traceback next to every `Error moving file`
line. The exception class discriminates H2/H3 and decides whether Step 3
below is sufficient on its own:

```bash
kubectl --context svc1751d-co2-calculator-dev/… -n svc1751d-co2-calculator-dev \
  logs -l app.kubernetes.io/name=co2-calculator-backend --since=48h --tail=-1 \
  | grep -A 20 'Error moving file'
# repeat for the worker deployment
```

Dev-cluster credentials were expired while writing this plan, so this is
**open**. Nothing below is blocked by it except the sizing numbers.

## The fix

### Step 1 — bounded idempotent retry at the single choke point

`DataIngestionProvider._move_to_processing`, in `base_provider.py`. All
four CSV providers route through it, so this is one guard instead of
four.

- **A failed attempt is either a raised exception (S3) or a falsy return
  (local)** — fact 4. The helper treats both as the same retryable
  failure. Do **not** delete the falsy-return branch: on the local store
  it is still the only failure signal, and dropping it would let a failed
  move fall through to `get_file(processing_path)` on a file that is not
  there — a silent fallback introduced by a fix whose whole point is
  removing silent failure. `_diagnose_move_failure` stays for the same
  reason: on local, the dependency swallows the exception, so that probe
  is the only detail available.
- Catch `Exception` from the destination probe too: in 1.2.0
  `path_exists` correctly raises on anything that is not a 404 (a
  permission or transport fault is not "the file is absent"), so a
  transport fault can surface on either call.
- Re-check `file_exists(processing_path)` at the top of every attempt.
  That check already exists from #1559 and is what makes the retry
  idempotent — a copy that succeeded before the connection dropped is
  detected, not redone.
- ~4 attempts, exponential backoff with jitter (0.25 / 0.5 / 1.0 s), then
  **raise**. No swallow, no fallback, no "misc" outcome. Zero added
  latency on the happy path.
- `_move_to_processed` reuses the same helper but keeps its non-raising
  caller: the data is already committed there, only archival bookkeeping
  is at stake, and that is a deliberate, documented asymmetry.

Keep the helper under 40 lines and 2 nesting levels; imports at top.

**Scope this brings with it** (so the estimate is honest): the two stale
docstrings from fact 4, plus the existing tests that pin the old
single-shot behaviour and will need rewriting rather than just extending
— `test_base_provider.py` (lines 103, 122, 134, 183, 198, all
`move_file = AsyncMock(return_value=False)`),
`test_base_factor_csv_provider.py::test_finalize_and_commit_move_file_failure`,
and `test_base_csv_provider.py` around line 1418. They must keep
asserting that an exhausted retry still fails loudly.

### Step 2 — one `S3Service` per process, with a sized pool (atomic)

- Replace the four per-provider `make_files_store()` calls with the
  process-wide singleton already in `app/api/v1/files.py`.
- Add `S3_MAX_POOL_CONNECTIONS` to `Settings` (default 32 ≈
  `MAX_CONCURRENT_JOBS × 8`, sized to cover concurrent jobs plus
  concurrent uploads on one pod) and pass it to `S3Service`.
- Close it in the FastAPI lifespan shutdown.

**These ship together, not separately.** Consolidating onto the singleton
without raising the pool would move job traffic onto the same
10-connection pool the upload endpoint uses — creating contention on a
path that currently works.

Two wrinkles to settle in review:

- `close()` exists on `S3Service` only, not on `FilesStore` /
  `LocalFilesStore`, so the lifespan hook needs an
  `isinstance(files_store, S3FilesStore)` discriminator. The cleaner
  alternative is adding `async def close()` to the `FilesStore` base
  upstream in `enacit4r-files` and bumping the tag. **Maintainer picks.**
- The three providers use inline `from app.api.v1.files import
  make_files_store` imports to dodge a circular import (against the
  imports-at-top rule). Importing the singleton has the same problem, so
  either keep the inline import or move `make_files_store` out of
  `api/v1/files.py` into a service module. Prefer the move.

### Step 3 — botocore retry tuning, zero code

`enacit4r-files` documents `AWS_RETRY_MODE` / `AWS_MAX_ATTEMPTS` as the
supported knobs. Set `AWS_RETRY_MODE=standard` and `AWS_MAX_ATTEMPTS=5`
on the backend and worker deployments in the chart. `standard` mode
retries a broader, better-defined set (throttling including `SlowDown`,
5xx, connection errors) than the `legacy` default. **Ship this first** —
if the traceback shows a `ClientError`, it may absorb H3 on its own, and
it is a one-line revert.

### Explicitly out of scope

Park as follow-up issues unless the maintainer says otherwise: `tmp/`
orphan GC; making a move-failed job recoverable without re-upload;
replacing the timestamp folder name with a `uuid4`.

## Regression tests

Deterministic, in CI — `backend/tests/unit/services/data_ingestion/test_base_provider.py`,
mirroring the #1559 tests already there. Patch `asyncio.sleep` so the
backoff costs nothing.

| Test | Setup | Fails today because |
| ---- | ----- | ------------------- |
| `…retries_transient_storage_error` | `file_exists` → False; `move_file` `side_effect=[S3Error(…), True]` | the first exception propagates; there is no retry (S3 contract) |
| `…retries_falsy_move_return` | `move_file` `side_effect=[False, True]` | a falsy return fails the job on the first try (local-store contract — the half a catch-only fix would break) |
| `…raises_after_exhausting_retries` | `move_file` always raises | (guards the fix: the error must still escape — no silent fallback — and the attempt count must be bounded) |
| `…rechecks_destination_between_attempts` | `move_file` raises once, then `file_exists` → True | asserts `move_file` awaited exactly once: idempotency must hold *across* retries, not just across job attempts |
| `…retries_when_existence_probe_fails` | `file_exists` `side_effect=[S3Error(…), False]` | a probe fault must be retried, never misread as "destination absent" |
| `…providers_share_one_files_store` | assert `provider.files_store is` the process singleton | each provider builds its own `S3Service` today |

Acceptance gate — manual, against dev + S3, the actual reproduction:

```bash
make perf-load PERF_CLASSES=CsvUploadUser PERF_USERS=20 PERF_TIME=10m
```

Pass = `FLOW csv upload e2e` failure rate ≤ the local-store baseline
(0.8%) **and** zero `Error moving file` lines in the pod logs for the
window. Run the 5-user stage first as a cheap smoke.

## Rollout and verification

1. Ship **Step 3** (chart env) alone. One revert-able release, and it
   measures how much the retry knob buys on its own. Re-run the 5-user
   stage.
2. Ship **Steps 1 + 2**. Re-run 5, then 20.
3. Watch, before and after: `Error moving file` count, `Unclosed client
   session` warnings, pod fd count, event-loop lag (already reported by
   `app/tasks/_event_loop_lag.py`), and GlitchTip for `S3Error`.
4. Sweep `tmp/` for orphans left by the failed runs and record the count
   in the issue — it sizes the GC follow-up.

## Open questions

1. **The traceback** (blocks the ranking, not the plan): exception class
   from the dev pods for 2026-08-30 09:05–09:15 UTC. `ClientError` /
   `SlowDown` → Step 3 may be enough on its own. `ClientConnectorError` /
   `ConnectTimeoutError` → Steps 1 + 2 are load-bearing.
2. Were the 20-user failures spread evenly across the 10 minutes, or
   climbing? Climbing supports H2 (leak); flat argues against it.
3. What is the dev S3 endpoint (MinIO / Ceph RGW / AWS), and does it cap
   connections or request rate per client? That sets
   `S3_MAX_POOL_CONNECTIONS`.
4. `close()` on the `FilesStore` base upstream (cleaner, needs a tag
   bump), or an `isinstance` discriminator in the lifespan (no dependency
   change)?
5. Should the divergent `move_file` contract (fact 4 — S3 raises, local
   returns `False`) be aligned upstream in `enacit4r-files` in the same
   tag bump? Handling both app-side is the smaller diff today and is what
   this plan assumes, but it leaves a dependency whose two backends
   signal failure differently.
6. Do the `tmp/` GC and "recover a move-failed job without re-upload"
   ship here, or as follow-up issues?
