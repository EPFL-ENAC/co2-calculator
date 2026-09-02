---
status: in-progress
issue: 2528
last_updated: 2026-09-02
summary: "The reported 56%-at-20-parallel rate is void — an artifact of
  a split file store in the reporter's own test topology, not S3
  concurrency (see Correction below). What survives: the move is an
  unretried copy_object+delete_object, and the enacit4r-files 1.2.0 tag
  bump left the app's two backends signalling failure differently
  (S3 raises, local returns False) with dead code on the S3 side.
  Plan: bounded idempotent retry at the single choke point handling both
  signals, shipped now; client-pool sizing and retry-mode tuning
  deferred until a clean concurrency measurement exists."
---

# Concurrent CSV upload move failures (#2528)

**Goal:** no `Error moving file` reaches a user, and the app's move
handles both signals its two file-store backends can send on failure
(fact 4) instead of silently trusting one and dead-coding the other.

Found by the #2295 load suite (PR #2526). Read
[`2295-load-tests-locust.md`](./2295-load-tests-locust.md) for the
harness and [`1559-ingestion-idempotent-tmp-to-processing-move.md`](./1559-ingestion-idempotent-tmp-to-processing-move.md)
for the existing idempotency guard this plan builds on.

## Correction (2026-09-02): the 56% figure is void

The maintainer's own follow-up (issue #2528 comment, 2026-08-30T11:31Z)
pulled the actual exception out of `data_ingestion_jobs.meta.status_history`
for the dev-DB run:

```
An error occurred (NoSuchKey) when calling the CopyObject operation:
The specified key does not exist.
```

`NoSuchKey` is not a transient fault — the source object was never in
the bucket, because that run's `backend/.env` had `S3_BUCKET` commented
out (`FILES_STORAGE_PATH=./files_storage` active), so the local backend
process wrote every `temp-upload` to its own laptop disk while
`RUN_BACKGROUND_POLLER=False` handed the ingest jobs to the dev pods,
which correctly looked in S3 and found nothing. The 56% measured a split
file store, not concurrency, and **retrying the move would not have
helped** — retrying a copy of a key that does not exist just fails N
times.

**What this voids:** the 56% number itself, the "70× local/S3 gap" framing
in H3 below, and Open Questions 1–2 as originally posed (they existed to
size a rate that turns out not to exist).

**What survives, unaffected by the topology bug:** every finding below
came from reading the code, not from the 56% run, and none of it depends
on that number — facts 1, 3, 4, 5, 6, 7, and H1. The **local-store run's
3/378 failures (0.8%)** are the only measurement left standing, because
`NoSuchKey`-by-split-store cannot arise when both the upload and the job
run against the same local disk. That residue is real and still
unexplained — see "The one open measurement" below.

## The path, traced

One CSV upload flow crosses these:

| Step                         | Code                                                                                                 | S3 calls                                               |
| ---------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `POST /v1/files/temp-upload` | `backend/app/api/v1/files.py` → `files_store.write_file` into `tmp/<ts>/`                            | put_object + metadata sidecar                          |
| `POST /v1/sync/dispatch`     | job row, then `run_job` under the `MAX_CONCURRENT_JOBS=4` semaphore                                  | —                                                      |
| move                         | `DataIngestionProvider._move_to_processing` (`backend/app/services/data_ingestion/base_provider.py`) | head_object, **copy_object**, delete_object, + sidecar |
| read                         | `files_store.get_file(processing_path)`                                                              | get_object                                             |
| archive                      | `_move_to_processed`                                                                                 | head_object, copy_object, delete_object, + sidecar     |

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
   same-filesystem rename with no network at all. That asymmetry is why
   the S3 path can fail on a transient network fault where the local path
   structurally cannot — it is a mechanism, not (per the Correction above)
   a measured gap.

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

   | Store                       | On failure                                               |
   | --------------------------- | -------------------------------------------------------- |
   | `S3FilesStore.move_file`    | **raises `S3Error`**, original chained (their #24)       |
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
_Proven_ (fact 3), and sufficient on its own to explain the shape: fails
at 5 uploaders, worse at 20, near-zero on a store with no network. This
is the one certain defect, and it is worth fixing whatever turns out to
be underneath it.

**H2 — client accumulation from never calling `close()`.**
_Mechanism proven_ (fact 5), _magnitude untested_ — the 56% run it was
originally ranked against is void (Correction above), and no clean
S3-concurrency measurement has replaced it yet. At
`MAX_CONCURRENT_JOBS=4` × 2–3 replicas and ~18 flows/min the
accumulation is bounded, and aiohttp closes transports on GC, so this
mechanism is real but its contribution to any real-world rate is
unknown until a valid-topology run exists.

**H3 — endpoint-side throttling or connection caps on the S3-compatible
store.** _Suspected, untested._ The scaling-with-concurrency signal it
was ranked on came from the void 56% run — there is currently no
evidence for or against this beyond the mechanism being plausible for
any S3-compatible store under load. Whether it would show as
503/`SlowDown` (which botocore `standard` retry mode absorbs by itself)
or `ClientConnectorError` / `ConnectTimeoutError` (which needs pool
sizing) cannot be decided from the code.

**H4 — `tmp/` path collision.** _Weak, confirmed weak by code._
`folder_name` is computed once per `POST /temp-upload` request
(`backend/app/api/v1/files.py:358-360`) as
`str(datetime.datetime.now(UTC).timestamp()).replace(".", "")` —
Python's `datetime.now()` carries microsecond resolution, so two
requests would need to land in the same microsecond _and_ pick the same
filename. `CsvUploadUser` draws from a handful of fixed filenames, so
the collision requires both conditions at once. At ~182 flows over 10
minutes the odds are tiny, and the symptom would be an occasional
"source no longer exists", not a large fraction of flows.

**H5 — a retry re-moving an already-moved file.** _Falsified_ in the
issue by `attempts = 1`, and independently by #1559's destination-exists
check already at the top of `_move_to_processing`.

### The one open measurement

The only real signal left after the Correction is the local-store run's
**3/378 failures (0.8%)** — on a store where the split-topology
`NoSuchKey` cannot arise, so these are genuine `tmp → processing`
failures. `LocalFilesStore.move_file` returns `False` rather than
raising, so these three went through the falsy-return branch and
`_diagnose_move_failure` (fact 4) — that diagnosis string, if the job
rows still exist, would say more than the code alone can. This session
has no network path to the dev DB (`co2-dev.postgresql.dbaas.intranet.epfl.ch`
is unreachable from outside the EPFL intranet) to pull it; whoever has
intranet + DB access should check `data_ingestion_jobs.meta.status_history`
for those three rows (if the local run was against the dev DB) or the
local run's own DB otherwise. Until then this is genuinely open, not
just unpursued — the plan should not read as if #2528 is closed once
Step 1 ships.

`logging.exception` also wrote a traceback next to every `Error moving
file` line in the void 56% run, but that traceback is no longer useful:
the Correction already identifies the exception (`NoSuchKey`) and its
cause (split topology), so pulling dev-pod logs for that window would
just confirm what is already known. **Do not re-run this kubectl
command** (kept here only so nobody re-derives it independently):

```bash
kubectl --context svc1751d-co2-calculator-dev/… -n svc1751d-co2-calculator-dev \
  logs -l app.kubernetes.io/name=co2-calculator-backend --since=48h --tail=-1 \
  | grep -A 20 'Error moving file'
```

## The fix

**Scope decision (maintainer, PR #2535, 2026-08-30T11:49Z):** "Fix the
`enacit4r-files` contract drift app-side now, and upstream too... Keep
the plan; drop the priority until a clean measurement exists." Read
against the Correction above, that means: **Step 1 ships now** — it is
the contract-drift fix (fact 4, handling both signals) and is correct
regardless of what any concurrency measurement eventually shows. **Steps
2 and 3 are deferred** — both were sized and ordered against the void
56% run (pool sizing against an assumed connection-exhaustion rate,
"ship Step 3 first" against an assumed throttling signal); revisit them
once a clean-topology measurement exists to size against.

### Step 1 — bounded idempotent retry at the single choke point (ship now)

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

### Step 2 — one `S3Service` per process, with a sized pool (atomic, deferred)

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

### Step 3 — botocore retry tuning, zero code (deferred)

`enacit4r-files` documents `AWS_RETRY_MODE` / `AWS_MAX_ATTEMPTS` as the
supported knobs. Set `AWS_RETRY_MODE=standard` and `AWS_MAX_ATTEMPTS=5`
on the backend and worker deployments in the chart. `standard` mode
retries a broader, better-defined set (throttling including `SlowDown`,
5xx, connection errors) than the `legacy` default. Cheap and a one-line
revert, but there is no longer a traceback or a rate to justify shipping
it ahead of a measurement — revisit alongside Step 2.

### Explicitly out of scope

Park as follow-up issues unless the maintainer says otherwise: `tmp/`
orphan GC; making a move-failed job recoverable without re-upload;
replacing the timestamp folder name with a `uuid4`.

## Regression tests

Deterministic, in CI — `backend/tests/unit/services/data_ingestion/test_base_provider.py`,
mirroring the #1559 tests already there. Patch `asyncio.sleep` so the
backoff costs nothing.

| Test                                     | Setup                                                               | Fails today because                                                                                            |
| ---------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `…retries_transient_storage_error`       | `file_exists` → False; `move_file` `side_effect=[S3Error(…), True]` | the first exception propagates; there is no retry (S3 contract)                                                |
| `…retries_falsy_move_return`             | `move_file` `side_effect=[False, True]`                             | a falsy return fails the job on the first try (local-store contract — the half a catch-only fix would break)   |
| `…raises_after_exhausting_retries`       | `move_file` always raises                                           | (guards the fix: the error must still escape — no silent fallback — and the attempt count must be bounded)     |
| `…rechecks_destination_between_attempts` | `move_file` raises once, then `file_exists` → True                  | asserts `move_file` awaited exactly once: idempotency must hold _across_ retries, not just across job attempts |
| `…retries_when_existence_probe_fails`    | `file_exists` `side_effect=[S3Error(…), False]`                     | a probe fault must be retried, never misread as "destination absent"                                           |
| `…providers_share_one_files_store`       | assert `provider.files_store is` the process singleton              | each provider builds its own `S3Service` today                                                                 |

Acceptance gate for Step 1 is the six unit tests above (CI, deterministic).
The load-test acceptance gate below is for **Steps 2/3, once they are
un-deferred** — do not run it to validate Step 1 alone, and do not run
it at all until the topology is fixed:

```bash
make perf-load PERF_CLASSES=CsvUploadUser PERF_USERS=20 PERF_TIME=10m
```

**Do not fire this against the current `backend/.env`** — it points at
the shared dev DB (`co2-dev.postgresql.dbaas.intranet.epfl.ch`), and per
the Correction above, a run with `S3_BUCKET` commented out reproduces
the split-topology bug, not a real measurement. Getting a clean number
first requires one process to both serve `temp-upload` and execute the
job (poller ON, `S3_BUCKET` actually uncommented, or a run driven
through a real deployment's public API) — see the maintainer's
"How to get a real number" note on issue #2528.

Pass, once run cleanly = `FLOW csv upload e2e` failure rate ≤ the
local-store baseline (0.8%) **and** zero `Error moving file` lines in
the pod logs for the window. Run the 5-user stage first as a cheap
smoke.

## Rollout and verification

1. **Ship Step 1 now** (contract-drift fix, maintainer-approved). CI
   gate only — no perf-load run needed to ship this, since it is correct
   independent of any concurrency rate.
2. **Open the upstream `enacit4r-files` PR** aligning the two backends'
   `move_file` contract (Open Question 5) — the maintainer has said they
   will do this; track it here rather than leave it silently assumed
   done.
3. **Get a clean concurrency measurement** (topology fixed, per the
   Correction) before reviving Steps 2/3. Re-run 5-user, then 20-user.
4. If the clean run still shows meaningful S3-path failures, ship
   **Steps 2 + 3** together (they are sized against each other — see the
   "ship together" note in Step 2) and watch, before and after:
   `Error moving file` count, `Unclosed client session` warnings, pod fd
   count, event-loop lag (`app/tasks/_event_loop_lag.py`), and GlitchTip
   for `S3Error`.
5. Sweep `tmp/` for orphans left by any failed runs (including the void
   56% run and the 3 local failures) and record the count in the issue —
   it sizes the GC follow-up (Open Question 6).

## Open questions

1. ~~The traceback~~ **Answered, and void.** The maintainer pulled it
   from `meta.status_history`: `NoSuchKey` on `CopyObject`, caused by the
   split file store, not a transient fault (see Correction). No dev-pod
   log fetch needed or wanted for this window.
2. ~~Flat vs climbing~~ **Void.** This existed only to decide between H2
   and H3 for a 56% rate that does not exist. Revisit only once a clean
   S3-concurrency run produces a real rate to characterize.
3. What is the dev S3 endpoint (MinIO / Ceph RGW / AWS), and does it cap
   connections or request rate per client? Still relevant for sizing
   `S3_MAX_POOL_CONNECTIONS` **if** a clean measurement later shows
   Step 2 is warranted — not urgent before then.
4. `close()` on the `FilesStore` base upstream (cleaner, needs a tag
   bump), or an `isinstance` discriminator in the lifespan (no dependency
   change)? Only matters once Step 2 is un-deferred.
5. **Answered (maintainer, PR #2535, 2026-08-30T11:49Z):** align the
   divergent `move_file` contract upstream in `enacit4r-files`, in
   addition to handling both signals app-side (Step 1). No upstream PR
   exists yet as of 2026-09-02 (checked `EPFL-ENAC/enacit4r-files` open
   PRs/issues) — the maintainer said they would open it; track that here
   rather than assume it is done.
6. Do the `tmp/` GC and "recover a move-failed job without re-upload"
   ship here, or as follow-up issues? Still open. Also still open: the
   3/378 local-store failures (0.8%) have no diagnosis yet — see "The one
   open measurement" above — so #2528 should stay open even after Step 1
   ships, not be closed as resolved.
