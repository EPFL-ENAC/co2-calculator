---
status: delivered
last_updated: 2026-05-05
summary: Two-path principle for the data pipeline (interactive sync vs bulk async).
---

# Data pipeline: the two-path principle

The CO2 calculator handles two very different write workloads, and they need
two very different runtime shapes. **Path 1 — Interactive UI** serves end users
editing a single module: latency below 200 ms, instant feedback, one row touched.
**Path 2 — Bulk operator** serves principal users and backoffice staff uploading
CSVs, syncing factors, and recomputing emissions: minutes of work, thousands of
rows, multiple stages chained together. Forcing both into one model breaks
either UX (sync work blocks request handlers) or operator scale (async chains
add latency to a single-row edit).

The two-path principle keeps them separate. Path 1 stays inline and synchronous.
Path 2 runs as a chain of async jobs claimed atomically by web pods and watched
by an in-process safety-net poller.

## Both paths at a glance

```mermaid
flowchart LR
    subgraph P1["Path 1 - Interactive UI (sync)"]
        U[User] -->|PATCH /api/v1/modules/{unit_id}/{year}/{module_id}/{submodule_id}/{item_id}| H1[Sync handler]
        H1 -->|inline write| DB1[(carbon_reports.stats)]
        DB1 -->|HTTP 200 + payload| U
    end

    subgraph P2["Path 2 - Bulk operator (async)"]
        OP[Operator] -->|POST /api/v1/sync/dispatch CSV| H2[Dispatch handler]
        H2 -->|enqueue| J1[csv_ingest job]
        J1 -->|chain| J2[module_emission_recalc job per type]
        J2 -->|writes| DB2[(carbon_reports.stats)]

        POLL[10s safety poller] -.->|claims orphans| J1
        POLL -.->|claims orphans| J2

        OP <-->|GET /api/v1/sync/jobs/{job_id}/stream SSE| J1
    end

    classDef p1 fill:#e0f7f5,stroke:#0d8a7e
    classDef p2 fill:#fef6e4,stroke:#c8851a
    class U,H1,DB1 p1
    class OP,H2,J1,J2,DB2,POLL p2
```

Path 1 returns the result on the same HTTP response. Path 2 returns a job id;
operators stream progress over SSE until the chain settles.

## Job lifecycle on Path 2

A Path 2 job moves through four states from `IngestionState`
(`NOT_STARTED → QUEUED → RUNNING → FINISHED`), with success or failure recorded
on a separate `IngestionResult` enum (`SUCCESS | WARNING | ERROR`). The
transition from `QUEUED` to `RUNNING` is the load-bearing one: it must be
atomic so that two pods racing to claim the same job cannot both win.

```mermaid
stateDiagram-v2
    [*] --> NOT_STARTED: enqueue
    NOT_STARTED --> QUEUED: dispatcher picks up
    QUEUED --> RUNNING: claim_job (atomic on state + is_current)
    RUNNING --> FinishedSuccess: handler returns ok
    RUNNING --> FinishedError: handler raises
    FinishedSuccess --> [*]
    FinishedError --> [*]

    note right of NOT_STARTED
        Picked up by:
        - fast path (fire_and_forget on the
          dispatch handler)
        - safety poller (every 10 s,
          NOT_STARTED sweep with
          SELECT ... FOR UPDATE SKIP LOCKED)
    end note

    note right of RUNNING
        claim_job is a two-step UPDATE
        inside a SAVEPOINT:
        1. demote prior is_current siblings
           that are not RUNNING
        2. atomic UPDATE-RETURNING flips
           the row to RUNNING + is_current.
        Race losers fall out via empty
        RETURNING or IntegrityError on the
        partial unique index
        UNIQUE(module_type_id,
               data_entry_type_id,
               target_type,
               ingestion_method,
               year)
        WHERE is_current = true.
    end note

    state FinishedSuccess: FINISHED (SUCCESS / WARNING)
    state FinishedError: FINISHED (ERROR)
```

Once a job reaches `FINISHED`, the handler may chain the next job in the same
event loop (fast path) or rely on the poller to pick it up (safety net).

## When to use which path

Use **Path 1 (sync)** when:

- A user is waiting on the response in the browser.
- The work touches one row (or a small bounded set).
- The result must appear in the next render.
- Examples: editing a `DataEntry`, toggling a module setting, deleting a row.

Use **Path 2 (async)** when:

- A whole CSV, factor set, or module-wide recalculation is involved.
- The work fans out across thousands of rows or multiple data-entry types.
- The caller is an operator who can wait minutes and watch SSE progress.
- Examples: `POST /api/v1/sync/dispatch`, `POST /api/v1/sync/factors/...`,
  `POST /api/v1/sync/units`, `POST /api/v1/sync/recalculate-emissions/...`.

If a request feels like Path 1 but starts to time out under realistic data,
move it to Path 2 rather than letting the sync handler bloat. If a request
feels like Path 2 but the data set is always tiny, keep it on Path 1 — a job
chain for one row is pure overhead.

## Cross-references

- ADR-010 — [Background Job Processing](../architecture-decision-records/010-background-job-processing.md):
  the original sync vs. async background-job evaluation (Celery + Redis vs.
  in-process). See ADR-015 / ADR-016 (when landed) for the two-path principle
  and the atomic `claim_job` transition that ship today.
- Implementation plan — [310-overview](https://github.com/epfl-enac/co2-calculator/blob/main/docs/implementation-plans/310-overview.md):
  the canonical statement of the two-path principle, plus Plans A–D that codify
  it for the bulk path (pod safety, factor pipeline, DAG handler registry, and
  the responsibility split that makes Path 2 pure async).

Future ADRs on the two-path principle and the `claim_job` atomic transition
will be linked here once they land.
