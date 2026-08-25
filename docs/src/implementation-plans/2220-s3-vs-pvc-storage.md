---
status: delivered
issue: 2220
last_updated: 2026-08-25
title: "S3 HeadObject 404s: root cause, and the S3-vs-stop-vs-PVC decision"
summary: "Root cause found live on 2026-08-25: the genuine 'Failed to move file' failures happen when a laptop running `make dev` with .env pointed at the shared dev DB polls and claims dev's ingestion jobs, then resolves their uploaded files against its own LocalFilesStore — the file sits untouched in S3 the whole time. Fixed with a fail-closed boot guard (assert_poller_isolation). The recurring HeadObject-404 error spans are expected, already-handled existence checks from the #1559 idempotent-move fix, mis-flagged by OTel's botocore auto-instrumentation — confirmed by correlating a live 'error' trace with its succeeding job. PVC is not adopted: dev already runs 3 backend replicas + 1 worker pod needing ReadWriteMany, and no RWX storage class is evidenced anywhere in the ops repo."
---

# S3 HeadObject 404s: root cause, and the S3-vs-stop-vs-PVC decision

Investigation for
[co2-calculator#2220](https://github.com/EPFL-ENAC/co2-calculator/issues/2220).
Builds on the upload-path work in
[#2261](https://github.com/EPFL-ENAC/co2-calculator/pull/2266) and the
already-shipped idempotent-move fix in
[#1559](1559-ingestion-idempotent-tmp-to-processing-move.md). Read
[#1402's plan](1402-trim-down-alerting.md) for the surrounding alerting
work — its earlier, abstract S3/PVC/local-staging comparison has since been
rewritten out of that document, and this doc grounds the comparison in the
actual bug and the actual dev cluster topology instead.

## Root cause

> **2026-08-25 update — the genuine failures are now root-caused, live.**
> A `Failed to move file … source no longer exists` failure was reproduced
> in dev (jobs 90 and 92) while the earlier jobs of the same day (3–87)
> had all succeeded. The discriminator was `data_ingestion_jobs.locked_by`:
> the succeeding jobs were claimed by `co2-calculator-worker-…` (the dev
> worker pod); the failing ones by `ENACITM-C018252` — a **laptop** running
> `make dev` with `backend/.env` pointed at the shared dev database
> (started 14:23, failures start 14:41). `RUN_BACKGROUND_POLLER` defaults
> to true, so the laptop's poller claimed dev's freshly-created CSV jobs;
> with no S3 credentials locally, `make_files_store()` fell through to
> `LocalFilesStore`, which looked for the uploaded file in `./files_storage`
> — hence "source no longer exists" seconds after a successful upload,
> while the object sat untouched in S3's `tmp/`. DB-only jobs
> (emission_recalc, aggregation) claimed by the laptop _succeeded_, which
> is why the symptom only ever hit file-backed jobs. The 2026-08-20
> incident (12 of 14 uploads failing during working hours, "self-healing"
> outside them) matches this mechanism exactly; its job rows were lost to
> a DB reseed, so its `locked_by` can no longer be checked directly.
>
> Fix shipped in this PR: `assert_poller_isolation` in `app/main.py` — a
> boot-time lifespan check (per the guardrails' "boot-time config checks
> live in the FastAPI lifespan") that refuses to start a
> `LOCAL_ENVIRONMENT=True` instance whose poller would claim jobs from a
> non-local DB host, with regression tests in
> `tests/unit/core/test_startup_checks.py`. The pod-heartbeat work (#1080)
> had already flagged this exact hazard ("a dev branch running locally
> against the stage DB silently collided with the deployed stage app") but
> only _surfaced_ it; this closes it.
>
> §1 below was also confirmed live the same day: a worker "error" trace
> (single root `S3.HeadObject` 404 span, `exception.escaped: false`,
> 14:38:50) correlated with job 75, which **succeeded** — the span is the
> `_move_to_processing` idempotency pre-check. The sections below predate
> the reproduction and stand as the (correct but then-incomplete)
> elimination work.

**Two separate things are being conflated by the issue's framing, and
they need separate fixes.**

### 1. Most of the "32 HeadObject 404s" are expected, already-handled checks — not bugs

The only two `head_object` call sites in the whole S3 client
(`enacit4r_files/services/s3.py`) are:

- `S3Service.path_exists` (`s3.py:68-88`), used by `S3FilesStore.file_exists`
  — wraps the call in a blanket `except Exception: return False` with
  **no logging at all**.
- `S3Service._upload_fileobj` (`s3.py:555`), called right after `put_object`
  during upload, with **no** surrounding `except` — a 404 there would
  `escape` (propagate) and fail the upload outright.

The one trace attached to the issue
([`Trace-ecd35e-2026-08-20 14_14_36.json`](https://github.com/user-attachments/files/31263688/Trace-ecd35e-2026-08-20.14_14_36.json))
is a single `S3.HeadObject` span, `status.code=ERROR`, from the `worker`
service in `svc1751d-co2-calculator-dev`, with
**`exception.escaped: false`**. Since only `path_exists()` catches the
exception before it can escape, this attribute uniquely fingerprints the
span as a `file_exists()` call that the application already handled
gracefully — not an unhandled failure. `exception.escaped: false` is proof
of that, not a hint.

`file_exists()` is called as a **destination-existence pre-check** in the
already-shipped #1559 idempotency fix
(`backend/app/services/data_ingestion/base_provider.py:64-108`):

```python
async def _move_to_processing(self, tmp_path: str) -> str:
    processing_path = f"processing/{self.job_id}/{filename}"
    if await self.files_store.file_exists(processing_path):   # <- HeadObject
        ...  # skip: prior attempt already moved it here
    ...
```

`_move_to_processed` does the identical check for `processed/<job_id>/`.
**On every successful, non-retried CSV ingestion job — the normal case —
both checks return 404, by design**: the destination genuinely doesn't
exist yet, and the code is asking "did a prior attempt already do this?"
before doing it. OTel's botocore auto-instrumentation marks the span
`ERROR` because `aiobotocore` raised a `ClientError` internally, entirely
independent of whether the application code around it catches that
exception one frame later. This is the standard "instrumented library
raises, app catches" false-positive pattern.

**Falsifiable prediction:** if this is the dominant source, dev should see
**≈2 expected 404 HeadObjects per successfully-finished `DataIngestionJob`**
(one from `_move_to_processing`, one from `_move_to_processed`), so 32 in
24h predicts **≈16 finished jobs** in that window, give or take a few
genuine failures (below). Confirm with: count of `data_ingestion_job` rows
with `state=FINISHED` in `svc1751d-co2-calculator-dev` over the same 24h
window that produced the 32 count, cross-referenced against the trace
timestamps. If dev only ran, say, 3 jobs in that window, this explanation
is wrong and a different source (e.g. a genuinely-broken retry loop) is
producing the extra 404s — re-open the investigation from there rather
than trusting this doc.

### 2. The genuine "Failed to move file" failures were unexplained by design — two layers of swallowing

When a move genuinely fails (destination absent, `move_file()` itself
returns `False`), the exact question the issue asks — _"why does the
application expose the error as 'Failed to move file' instead of exposing
the underlying 404?"_ — has a precise answer:

1. **`S3FilesStore.move_file`** (vendored `enacit4r-files@1.0.0`,
   `s3.py:886-915`) wraps its entire copy+delete operation in
   `except Exception as e: logging.error(...); return False` — the real
   `botocore.exceptions.ClientError` (type, message, request ID) is
   discarded into a bare bool. `S3Service.path_exists` (`s3.py:68-88`) is
   worse: it doesn't even log.
2. **`DataIngestionProvider._move_to_processing`** (this repo,
   `base_provider.py`, pre-fix) then raised a generic
   `Exception(f"Failed to move file from {tmp_path} to {processing_path}")`
   — the only information left by that point is which two paths were
   involved, nothing about _why_.

Neither layer is a data-loss race by itself. The job-claim path
(`backend/app/repositories/data_ingestion.py:1282-1295`,
`FOR UPDATE SKIP LOCKED` on `locked_by IS NULL`) already prevents two
workers from claiming the same job row, and #1559's destination-exists
check already prevents a crash-and-retry from re-consuming an
already-moved `tmp/` source. The residual "no-heartbeat duplicate-run"
hazard flagged by `sweep_stuck_running_jobs`'s own docstring (tracked as
Plan 310C) is a separate, already-tracked risk — out of scope here per the
guardrails (pipeline/recalculation internals need their own reviewed
plan).

**This repo can't fix layer 1** — `enacit4r-files` is pulled by git tag,
not forked (per AGENTS.md, and per PR #2266's identical finding about the
double `PutObject`/`HeadObject`). Filed upstream instead:
[enacit4r-files#24](https://github.com/EPFL-ENAC/enacit4r-files/issues/24).
**Layer 2 is fixed in this PR** — see [Implemented](#implemented) below.
The fix diagnoses _why_ a move failed (source gone vs. source present) by
asking `file_exists()` again at the failure point; this is the best this
repo can do without the upstream fix, and it still leaves the true
storage-level exception undiscoverable until `enacit4r-files` stops
swallowing it.

## Architecture decision: S3 vs stop-using-S3 vs PVC

**Options 2 ("stop using S3") and 3 ("use a PVC") collapse into the same
option once you look at how many pods actually need the file.** "Stop
using S3" means `make_files_store()` (`backend/app/api/v1/files.py:40-80`)
falls through to `LocalFilesStore` (`enacit4r_files/services/local.py`) at
a container-local path (`settings.FILES_STORAGE_PATH`) whenever
`S3_ENDPOINT_HOSTNAME`/`S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY` aren't
set. A container-local path with **no shared volume** means the pod that
uploaded the file and the pod that processes it may be looking at two
different, unrelated filesystems — that isn't an alternative storage
backend, it's a broken config. So the real three-way choice is: **(1) fix
S3 as currently used, (2) local storage on a shared PVC, or nothing**.

### Is `LocalFilesStore` safe for concurrent multi-pod access on a shared volume?

Read in full (`enacit4r_files/services/local.py`). Findings:

- `move_file` (`local.py:308-345`) uses `shutil.move()`, which tries
  `os.rename()` first — **atomic on POSIX when source and destination are
  on the same filesystem**, which they are here (`tmp/`, `processing/`,
  `processed/` are all subdirectories under one `base_path`). This is safe
  _if_ the underlying network filesystem honors POSIX rename atomicity
  (CephFS and NFSv4 do; older NFSv3 implementations have historically had
  caveats — needs confirming against whatever EPFL's cluster actually
  provisions, see below).
- Per-job paths (`processing/<job_id>/<filename>`) are already namespaced
  by `job_id`, and the DB-level `FOR UPDATE SKIP LOCKED` claim prevents two
  workers from ever operating on the same job concurrently — so the
  write-write race a naive multi-pod PVC setup would normally worry about
  doesn't actually arise here; paths across concurrent jobs never collide.
- The same blanket-`except`-swallows-the-real-error pattern exists here
  too (`move_file`/`copy_file`/`file_exists`, `local.py:264-269, 300-306,
339-345`) — a PVC swap would not by itself fix the "Failed to move file"
  observability gap; it would just change which backend's exception gets
  swallowed. The app-level diagnosis fix in this PR helps identically for
  both backends.
- **Conclusion: `LocalFilesStore` is structurally fine for concurrent
  multi-pod access, conditional on the storage class actually providing
  atomic POSIX rename** — the code doesn't introduce a new race beyond
  what any RWX-mounted store would have.

### Does dev have (or can it get) an RWX-capable PVC?

**No — and dev's own topology makes RWO structurally insufficient,
independent of storage-class availability.**
`openshift-app-config/epfl/co2-calculator/overlays/dev/kustomization.yaml`
runs **3 backend replicas + 1 separate worker pod**
(`worker.enabled=true`, confirmed live by the trace's own
`k8s.pod.name: co2-calculator-worker-84769ffb78-hdqhk`, and by the
overlay's own comment: _"dev runs 3 backend + 1 worker = up to 120
possible [connections]"_). A `ReadWriteOnce` PVC binds to a single node;
with 4 pods across a Deployment + a separate worker Deployment, OpenShift
gives no guarantee they land on the same node — an RWO PVC would routinely
leave the worker (or two of the three backend replicas) unable to see
files the others wrote. **This isn't a hypothetical — dev is already
running with that topology today.**

`ReadWriteMany` is therefore required, and **no RWX-capable storage class
is evidenced anywhere in the ops repo.** The only `PersistentVolumeClaim`
in the entire `openshift-app-config` repository — across every app, not
just this one — is `epfl/co2-calculator/base/pvc-db-dumps.yaml`, which
uses `storageClassName: thin-csi` with `accessModes: [ReadWriteOnce]`.
There is no `StorageClass` resource, no CephFS/NFS reference, and no
`ReadWriteMany` anywhere to confirm against (StorageClass objects are
cluster-level and provisioned by EPFL's OpenShift admins, not visible from
a GitOps overlay repo). Per the task's own guardrail — don't guess at
infrastructure with real data-loss failure modes — **this blocks
implementing the PVC swap now.**

**What would unblock it:** confirmation from EPFL's OpenShift/platform
team that an RWX storage class (CephFS-backed is the common choice)
exists and is available to this namespace, quoting the exact
`storageClassName` to use. Alternatively, if dev's topology were
deliberately collapsed to a single backend replica with the worker
disabled (`worker.enabled=false`, `backend.replicaCount=1`), an RWO PVC on
the already-precedented `thin-csi` class would work — but that's a
dev-environment regression (single point of failure, no realistic load
test of the multi-replica path dev is meant to mirror) traded for a
storage simplification, and is a call for the maintainers, not this PR.

## Decision

**Recommendation: Option 1 — fix S3 as currently used, do not adopt a
PVC.** The investigation found no architectural flaw in using S3 for this
workflow: the actual race conditions the issue worried about (duplicate
workers, crash-and-retry) are already closed by existing code
(`FOR UPDATE SKIP LOCKED` claiming, #1559's idempotent move). What
remained was (a) alert noise from expected, handled 404s being
misclassified as span errors, and (b) an app-level error message that lost
diagnostic value across two exception-swallowing layers. Both are
addressed without an architecture change:

- (a) is an observability/alerting-configuration problem, not a code bug —
  see [Left as a written proposal](#left-as-a-written-proposal-not-implemented-here).
- (b) is fixed at the one layer this repo owns (see below); the deeper fix
  belongs to `enacit4r-files` and is filed upstream.

PVC-for-dev is **not** adopted: dev's actual topology (3 backend + 1
worker) requires RWX, and no RWX storage class is evidenced in the ops
repo. Implementing it on an unconfirmed assumption risks exactly the
failure mode the guardrails warn about most — corrupting or losing
user-uploaded data on a storage backend that silently doesn't do what was
assumed.

## Implemented

- **(2026-08-25)** `backend/app/main.py`: `assert_poller_isolation` — the
  fail-closed boot guard for the actual root cause (local poller claiming
  shared-DB jobs, see the update at the top), with regression tests in
  `backend/tests/unit/core/test_startup_checks.py` and a warning note next
  to `RUN_BACKGROUND_POLLER` in `backend/.env.example`.
- `backend/app/services/data_ingestion/base_provider.py`:
  `_move_to_processing`/`_move_to_processed` now call a new
  `_diagnose_move_failure()` helper when `move_file()` returns `False`,
  distinguishing "source no longer exists" (a concurrent/prior attempt
  likely already consumed it) from "source still present, storage error
  unreported" — instead of the old bare "Failed to move file from X to Y".
  This is the most this repo can add without patching the vendored
  dependency; the real botocore/filesystem exception is still discarded
  one layer down (see below).
- Regression tests in
  `backend/tests/unit/services/data_ingestion/test_base_provider.py`
  covering both the missing-source and still-present-source diagnosis
  branches, on top of the existing #1559 idempotency coverage.
- Fixed `1559-ingestion-idempotent-tmp-to-processing-move.md`'s stale
  `status: proposed` frontmatter to `delivered` — the idempotent-move code
  it describes is already shipped and tested; the stale status cost real
  investigation time here re-confirming something already done.
- Filed [enacit4r-files#24](https://github.com/EPFL-ENAC/enacit4r-files/issues/24)
  for the upstream blanket-exception-swallowing in `S3Service.path_exists`
  / `S3FilesStore.move_file`/`copy_file`/`delete_file` — the real fix for
  "expose the underlying 404" needs to happen there, not in this repo.

## Left as a written proposal (not implemented here)

- **Alerting-noise fix (§1 above).** The two expected-404 `file_exists()`
  checks per successful job are legitimate application behavior, not a
  bug — the fix belongs in how they're alerted on, not in removing the
  idempotency checks that need them. Concretely: either (a) have the OTel
  Collector's `transform`/`filter` processor (already used for the
  `route_class` work in #1402) downgrade or drop span-error status for
  `S3.HeadObject` 404s specifically, since a 404 from an existence check
  is not, on its own, evidence of anything wrong; or (b) alert on the
  _rate_ of "Failed to move file" **application log lines** (a much rarer,
  always-genuine event) instead of on `S3.HeadObject` error-status spans.
  Not implemented here: alerting-rule ownership for this app currently
  sits with the active #1402 effort (`openshift-app-config` PRs #8-#11),
  and a one-off change from this investigation risks conflicting with that
  in-flight work. Filed as a note for whoever picks up #1402's remaining
  steps, not as a separate ops-repo PR from this branch.
- **PVC-for-dev**, pending the RWX storage-class confirmation described
  above.

## Verification

- `make ci` (ruff + ty backend): green.
- `uv run pytest tests/unit/services/data_ingestion/test_base_provider.py`:
  9 tests pass, including the 3 new regression tests.
- No `openshift-app-config` changes in this PR (none were safe to make
  without the RWX confirmation) — nothing to validate there.
