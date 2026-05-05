# 310-d — Bulk Path Pure Async (Path 2 only)

## Context

The CO2 calculator has two user paths with different latency expectations (see overview's
"two-path principle"):

- **Path 1 — Interactive UI**: standard / principal users edit modules via
  `POST/PATCH/DELETE /v1/carbon_reports/...`. Synchronous: DataEntry → emissions →
  module stats → report stats, all inline. Instant feedback.
- **Path 2 — Bulk operator**: principal users + backoffice métier upload CSVs, sync
  factors, sync units. No instant-feedback expectation; minutes are acceptable.

Today's bug surface is on Path 2: CSV ingest computes emissions inline (inside the ingest
transaction); factor recalculation also writes emissions; both call `recompute_stats` which
writes `carbon_reports`. Multiple concurrent bulk pipelines for different modules race on the
same tables.

This plan makes Path 2 fully respect "one writer per table." **Path 1 is explicitly out of
scope** — its inline emission compute is not a violation; it is a deliberate UX choice for
the interactive path.

Depends on: **Plan C** (handler registry, `chain_job` helper).

---

## Target table ownership (Path 2)

| Table                  | Path 2 sole writer               | Path 1 (unchanged)           |
| ---------------------- | -------------------------------- | ---------------------------- |
| `data_entries`         | `csv_ingest` / `api_ingest` jobs | `CarbonReportModuleWorkflow` |
| `data_entry_emissions` | `emission_recalc` job            | `CarbonReportModuleWorkflow` |
| `carbon_reports.stats` | `aggregation` job                | `CarbonReportModuleWorkflow` |

Path 1 still writes the same tables synchronously for single-row UI edits — but Path 1's
writes are scoped to one row, fast, and trivially serialized by the request. The race
conditions we are eliminating are bulk-path-only.

---

## What changes on the bulk path

### 1. Bulk ingest providers stop writing emissions

Today every `csv_ingest`, `api_ingest`, and `factor_ingest` provider calls
`DataEntryEmissionService.upsert_by_data_entry()` inside the ingest transaction. In Plan D
they don't.

After all `data_entries` are inserted/upserted, the ingest handler's post-success block calls
`chain_job(parent=job, job_type="emission_recalc", ...)` for each affected
`(module_type_id, data_entry_type_id)`.

For `csv_ingest` (single module/det per upload): one chained child.
For `factor_ingest` (already wired in Plan B): one chained child per stale (module, det)
— this part is **already** in Plan C's factor_ingest_handler. Plan D extends the same pattern
to csv_ingest and api_ingest.

### 2. `emission_recalc` stops calling `recompute_stats` directly

Today's `EmissionRecalculationWorkflow.recalculate_for_data_entry_type` ends with:

```python
for module_id in affected_module_ids:
    await CarbonReportModuleService.recompute_stats(...)
```

Plan D removes this. After the recalc handler commits, it calls:

```python
await chain_job(
    job, job_type="aggregation",
    module_type_id=job.module_type_id,
    year=job.year,
    session=job_session,
)
```

### 3. New `aggregation` handler

```python
@register("aggregation")
async def aggregation_handler(job, job_session, data_session):
    """
    Sole writer of carbon_reports.stats for the bulk path.
    Reads data_entry_emissions for (module_type_id, year), recomputes stats per
    affected CarbonReportModule, writes carbon_reports.stats with ON CONFLICT.
    """
    svc = CarbonReportModuleService(data_session)
    affected = await svc.list_modules_for(
        module_type_id=job.module_type_id, year=job.year
    )
    for module in affected:
        await svc.recompute_stats(module)   # existing method, unchanged internals
    return {"modules_refreshed": len(affected)}
```

### 4. Aggregation dedup (the N-jobs problem)

When `factor_ingest` fans out to N `emission_recalc` (one per stale det), each chains to
`aggregation` for the same `(module_type_id, year)` — that is N redundant aggregation jobs
per module.

**Dedup mechanism**: a partial unique index on **active** (NOT_STARTED or RUNNING)
aggregation jobs:

```sql
CREATE UNIQUE INDEX uq_aggregation_active
    ON data_ingestion_jobs (module_type_id, year)
    WHERE job_type = 'aggregation'
      AND state IN (0, 1, 2);    -- NOT_STARTED, QUEUED, RUNNING
```

`chain_job(job_type="aggregation", ...)` uses `INSERT ... ON CONFLICT DO NOTHING` against
this index. The first child to chain creates the aggregation job; subsequent siblings see
the existing pending one and skip. The aggregation job runs once after all recalcs in the
fan-out finish (or while later recalcs are still running — the aggregation reads the current
state of `data_entry_emissions` at execution time and produces a consistent snapshot for
that module).

`chain_job` extension:

```python
async def chain_job(..., dedup_active: bool = False, ...) -> Optional[int]:
    """
    If dedup_active=True, INSERT ... ON CONFLICT DO NOTHING against the
    uq_aggregation_active index (or equivalent for other dedupable types).
    Returns child id, or None if dedup'd.
    """
```

Aggregation handler is the only caller passing `dedup_active=True` initially. Future
dedupable job types (e.g. progress-bar refresh) can opt in.

---

## DAG shape after Plan D

```
csv_ingest / api_ingest / factor_ingest
    │
    ├─▶ emission_recalc (det A)  ──┐
    ├─▶ emission_recalc (det B)  ──┼──▶ aggregation (module X, year Y)
    └─▶ emission_recalc (det C)  ──┘            (deduplicated)
```

`pipeline_id` (set on the parent ingest job) propagates through every node; the dashboard
can show progress for the entire pipeline run.

---

## Frontend impact

### Stale-stats UX (the real spec)

Today `carbon_reports.stats` is loaded with the carbon report and displayed instantly. After
a bulk CSV upload, the stats are **stale** (reflect the previous data) until the chain
completes. We do not show 0; we show outdated values.

**Spec**:

1. Carbon report response includes `current_pipeline_id: Optional[UUID]` populated from the
   most recent unfinished pipeline whose any-job has this `module_type_id`.
2. If `current_pipeline_id` is set, the module card displays a "Recalculating..." badge and
   subscribes to `GET /sync/pipelines/{id}` (Plan C) for SSE updates.
3. Stats are visually de-emphasized (gray, with a note: "Updated through {last_finished_at}")
   until the pipeline finishes.
4. Once the `aggregation` job for that module completes, the badge clears and stats refresh.
5. Manual UI edits during the pipeline window are still synchronous (Path 1 untouched). The
   `recompute_stats` call from Path 1 does not race with the aggregation job — both use ON
   CONFLICT DO UPDATE on the same row; last write wins, which is correct behavior here.

### SSE flow

Frontend already has `GET /sync/jobs/{job_id}/stream`. Plan D adds
`GET /sync/pipelines/{id}/stream` (Plan C exposed the read endpoint; this adds streaming) so
the UI tracks the whole pipeline, not just the ingest step.

---

## Migration story (provider-by-provider rollout)

The bulk-path emission write is currently inside provider classes. Migrating each provider
is independent. Recommended sequence within Plan D's PR:

1. **factor_ingest provider** is already aligned in Plan B/C (no inline emission compute —
   it never had any).
2. **csv_ingest** providers (one per module): remove `upsert_by_data_entry` calls; add
   `chain_job(emission_recalc)` post-commit. Test each module's CSV in isolation before
   moving on.
3. **api_ingest provider** (travel): same pattern.
4. Add the `aggregation` handler.
5. Switch `emission_recalc` handler to chain to `aggregation` instead of calling
   `recompute_stats` inline.
6. Remove `recompute_stats` calls from `EmissionRecalculationWorkflow`.

A feature flag (`settings.BULK_PATH_PURE_ASYNC`) gates the new behavior so we can roll
forward and back if a provider's chain-job semantics turn out to need adjustment.

---

## Risks and mitigations

| Risk                                                                                  | Mitigation                                                                                                                                                                                                                                                                                             |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Stats appear stale longer than expected during pipeline run                           | Stale-stats UX above; badge + SSE keep operators informed                                                                                                                                                                                                                                              |
| `aggregation` runs while later `emission_recalc` siblings are still writing emissions | Aggregation reads current snapshot; produces correct stats for that snapshot. A second aggregation IS created (after dedup window expires) when the next sibling chains, ensuring eventual correctness.                                                                                                |
| Dedup index `uq_aggregation_active` blocks legitimate parallel modules                | Only blocks within same `(module_type_id, year)`. Different modules / years run in parallel.                                                                                                                                                                                                           |
| `csv_ingest` failure leaves data_entries written but emissions unchained              | Same recovery as today: `recalculation-status` shows the data is dirty; operator triggers manual recalc.                                                                                                                                                                                               |
| Path 1 inline edit during a Path 2 pipeline                                           | Both paths write `carbon_reports.stats` with ON CONFLICT DO UPDATE. The Path 1 write reflects the user's edit; the subsequent aggregation handler overwrites with bulk-path correct value. The window is small (Path 1 edit is ms; aggregation completes minutes later). Documented expected behavior. |

---

## Tests

| Test                               | Assertion                                                                                          |
| ---------------------------------- | -------------------------------------------------------------------------------------------------- |
| `csv_ingest` provider              | does NOT call `upsert_by_data_entry`                                                               |
| `csv_ingest` handler               | chains to `emission_recalc` on success; not on ERROR                                               |
| `emission_recalc` handler          | does NOT call `recompute_stats`                                                                    |
| `emission_recalc` handler          | chains to `aggregation` on success                                                                 |
| `aggregation` handler              | calls `recompute_stats` per module; writes carbon_reports.stats                                    |
| Aggregation dedup                  | N concurrent `chain_job(aggregation)` for same (module, year) — only 1 job created                 |
| Dedup across years                 | (module=X, year=2025) and (module=X, year=2026) — both jobs created                                |
| Full DAG integration               | csv_ingest → 1 emission_recalc → 1 aggregation; all FINISHED/SUCCESS; carbon_reports.stats updated |
| Fan-out integration                | factor_ingest → N emission_recalc → 1 deduplicated aggregation per module                          |
| Path 1 edit during Path 2 pipeline | manual edit succeeds inline; subsequent aggregation does not error                                 |
| Pipeline SSE stream                | `GET /sync/pipelines/{id}/stream` yields all child job updates                                     |

---

## Relevant files

- `backend/app/providers/` — every CSV/API ingest provider: remove emission writes, return data summary
- `backend/app/tasks/ingestion_tasks.py` — `csv_ingest_handler` and `api_ingest_handler` post-success: `chain_job(emission_recalc)`
- `backend/app/tasks/emission_recalculation_tasks.py` — `emission_recalc_handler`: remove `recompute_stats` call, add `chain_job(aggregation, dedup_active=True)`
- `backend/app/tasks/aggregation_tasks.py` (new) — `aggregation_handler`
- `backend/app/tasks/runner.py` — extend `chain_job` with `dedup_active: bool`
- `backend/app/services/carbon_report_module_service.py` — `recompute_stats` unchanged; new `list_modules_for(module_type_id, year)`
- `backend/app/api/v1/carbon_report.py` — response includes `current_pipeline_id`
- `backend/app/api/v1/data_sync.py` — `GET /sync/pipelines/{id}/stream` SSE endpoint
- `frontend/src/pages/back-office/DataManagementPage.vue` and module cards — "Recalculating..." badge + pipeline SSE
- `backend/app/core/config.py` — `BULK_PATH_PURE_ASYNC: bool = True` feature flag
- `backend/migrations/` — `uq_aggregation_active` partial unique index

---

## Follow-ups rolled in from PR #976 review

### Batch the rematch in `EmissionRecalculationWorkflow`

Plan B added a per-entry rematch in `recalculate_for_data_entry_type`
(`backend/app/workflows/emission_recalculation.py`):

```python
for entry in entries:
    refreshed = await handler_svc.resolve_primary_factor_id(
        handler=handler, payload=dict(entry.data),
        data_entry_type_id=data_entry_type_id, year=year,
        existing_data=None,
    )
    ...
```

This is **N+1**: one `resolve_primary_factor_id` call (and at least one factor query)
per data entry. Acknowledged in code as Plan D scope. Concrete shape for the fix:

1. Pull all factors for `(data_entry_type_id, year)` once, into a Python `dict` keyed
   by classification tuple (using `handler.kind_field` / `subkind_field` to derive
   the key).
2. Replace `resolve_primary_factor_id` per-entry call with a Python lookup against
   that dict.
3. Fall back to the existing per-entry path only when the lookup misses (e.g. a
   classification value the bulk-load query didn't see).

For the largest existing module (purchases ~10k entries), this collapses ~10k DB
roundtrips into one. Don't ship Plan D without this — the per-entry cost adds up
once we move emission writes out of the ingest path and into recalc-only.

### Two-pass partition in `FactorRepository.upsert_factors`

Minor: the upsert splits its input into `with_year` / `no_year` via two list
comprehensions. Single-pass with a defaultdict is cleaner and saves a list copy
on 50k-row uploads. Pure refactor, no behavior change — fits Plan D's broader
provider/repo audit.
