# 310-b — Factor Pipeline + Unit Sync Tracking

## Context

Three things to fix on the bulk path (Path 2):

1. **Factor ingest** today deletes all factors for a `(data_entry_type_id, year)` combo and
   re-inserts. This generates new `factor.id` values, orphaning any
   `DataEntry.primary_factor_id` FK pointing to the old rows (Strategy A entries: equipment,
   purchases, process_emissions, etc.). After the upload the recalculation step is manual —
   operators forget it.
2. **Factor classification ordering** is a footgun: `classification` is `Column(JSON)` and the
   unique index this plan introduces would be defeated by inconsistent key insertion order
   (silent duplicate rows). JSONB normalizes keys alphabetically and fixes this.
3. **Unit sync** (`POST /sync/units`) returns `job_id=0`. Untracked, no SSE, no recovery.

Depends on: **Plan A** (claim_job, locked_by, job_type, pipeline_id fields).

---

## Part 1 — Migrate `classification` to JSONB

The current `factors.classification` is `Column(JSON)`. Postgres `JSON` preserves the original
text form; `::text` reflects whatever order Python's `json.dumps` produced. Insertion order
across handlers is convention-based and one inconsistent caller silently creates a duplicate.

**Fix**: migrate to JSONB. Postgres normalizes JSONB key order alphabetically, so `::text` is
deterministic regardless of insertion order.

```sql
ALTER TABLE factors
  ALTER COLUMN classification TYPE JSONB USING classification::JSONB;
```

Update the SQLAlchemy model: `Column(JSONB)` from `sqlalchemy.dialects.postgresql`. Existing
read paths are unaffected — JSONB returns the same Python dict.

---

## Part 2 — Factor upsert-in-place + unique index

### Identity key

```
(data_entry_type_id, year, emission_type_id, classification)
```

### Migration (immediately after JSONB conversion above)

```sql
CREATE UNIQUE INDEX uq_factor_identity
    ON factors (data_entry_type_id, year, emission_type_id, (classification::text))
    WHERE year IS NOT NULL;

CREATE UNIQUE INDEX uq_factor_identity_no_year
    ON factors (data_entry_type_id, emission_type_id, (classification::text))
    WHERE year IS NULL;
```

Two partial indexes because `year IS NULL` rows would not enforce uniqueness with `year` in
the index expression (NULL ≠ NULL).

### `factor_repo.upsert_factors`

```python
async def upsert_factors(
    self, factors: list[Factor], current_job_id: int
) -> int:
    """
    Insert-or-update factors by identity key. Preserves factor.id for existing rows.
    Stamps last_seen_job_id so stale factors (not in this batch) can be detected.
    Returns count of rows affected.
    """
    if not factors:
        return 0
    payload = [
        {**f.model_dump(exclude={"id", "last_seen_job_id"}),
         "last_seen_job_id": current_job_id}
        for f in factors
    ]
    stmt = pg_insert(Factor).values(payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=["data_entry_type_id", "year", "emission_type_id",
                        func.cast(Factor.classification, String)],
        set_={
            "values": stmt.excluded.values,
            "last_seen_job_id": stmt.excluded.last_seen_job_id,
            "updated_at": func.now(),
        },
    )
    result = await self.session.execute(stmt)
    return result.rowcount
```

### Provider changes

Every factor CSV/API provider currently calls
`factor_service.bulk_delete_by_data_entry_type(...)` then bulk-inserts. Replace with
`factor_repo.upsert_factors(parsed_factors, current_job_id=job.id)`.

`bulk_delete_by_data_entry_type` is **kept** in the codebase for full-reset admin flows but is
no longer called from the normal ingest path.

Files to update: every provider class under `backend/app/providers/` that handles
`target_type=FACTORS`.

---

## Part 3 — Stale factor tracking (`last_seen_job_id`)

After the upsert, factors not in the new batch are silently kept (unlike the old
delete-and-reinsert behavior). To make this visible to operators:

```sql
ALTER TABLE factors
  ADD COLUMN last_seen_job_id INTEGER REFERENCES data_ingestion_jobs(id);

CREATE INDEX ix_factors_last_seen_job_id ON factors (last_seen_job_id);
```

Stale factors detected by:

```sql
SELECT f.*
  FROM factors f
  LEFT JOIN data_ingestion_jobs latest
    ON latest.module_type_id = ...        -- joined on the latest is_current
                                           --  factor job for this combo
 WHERE f.last_seen_job_id < latest.id;
```

Surface this in a separate read endpoint (e.g. `GET /factors/stale?year=2025`) — UI can warn
operators that some factors are no longer in the upload but are still referenced. **Not
deleted** because deletion would re-introduce dangling FKs.

---

## Part 4 — Auto-recalculation after factor ingest

### Trigger point

At the end of `run_sync_task` (`backend/app/tasks/ingestion_tasks.py`), after
`data_session.commit()` and before the final `_update_job(state=FINISHED, ...)`:

```python
if job.target_type == TargetType.FACTORS and final_result != IngestionResult.ERROR:
    await _enqueue_stale_recalculations(
        job_session,
        module_type_id=job.module_type_id,
        data_entry_type_id=job.data_entry_type_id,
        year=job.year,
        pipeline_id=job.pipeline_id or uuid4(),  # promote single job into a pipeline
    )
```

### `_enqueue_stale_recalculations`

```python
async def _enqueue_stale_recalculations(
    session: AsyncSession,
    *,
    module_type_id: Optional[int],
    data_entry_type_id: Optional[int],
    year: int,
    pipeline_id: UUID,
) -> None:
    """
    Create one emission_recalc job per stale (module, det) and fire each via
    asyncio.create_task. Children inherit pipeline_id from the parent factor job.
    """
    repo = DataIngestionRepository(session)
    rows = await repo.get_recalculation_status_by_year(year)
    targets = [
        r for r in rows
        if r["needs_recalculation"]
        and (module_type_id is None or r["module_type_id"] == module_type_id)
        and (data_entry_type_id is None or r["data_entry_type_id"] == data_entry_type_id)
    ]
    for row in targets:
        new_job = DataIngestionJob(
            job_type           = "emission_recalc",
            module_type_id     = row["module_type_id"],
            data_entry_type_id = row["data_entry_type_id"],
            year               = year,
            ingestion_method   = IngestionMethod.computed,
            target_type        = TargetType.DATA_ENTRIES,
            entity_type        = EntityType.MODULE_PER_YEAR,
            state              = IngestionState.NOT_STARTED,
            pipeline_id        = pipeline_id,
            run_after          = func.now(),
            meta               = {"config": {
                "year": year,
                "data_entry_type_id": row["data_entry_type_id"],
                "parent_job_id": current_job_id,
            }},
        )
        created = await repo.create_ingestion_job(new_job)
        await session.commit()
        # Fire chain via asyncio.create_task; safety poller picks up if pod crashes
        asyncio.create_task(
            run_recalculation_task(
                row["module_type_id"], row["data_entry_type_id"], year, created.id,
            )
        )
```

This helper becomes throwaway code once Plan C lands — Plan C generalizes it into
`chain_job(parent, job_type, ...)` used by every handler. We keep the implementation
self-contained in Plan B so each plan can ship independently.

---

## Part 5 — Unit sync job tracking

### Add `EntityType.GLOBAL_PER_YEAR`

```python
class EntityType(IntEnum):
    GLOBAL_PER_YEAR      = 1   # ← new: not scoped to a module
    MODULE_PER_YEAR      = 2
    MODULE_UNIT_SPECIFIC = 3
```

### Migration

`EntityType` uses `SAEnum(..., native_enum=True)` — adding a value requires altering the
Postgres enum type:

```sql
ALTER TYPE entity_type_enum ADD VALUE 'GLOBAL_PER_YEAR' BEFORE 'MODULE_PER_YEAR';
```

(Postgres ≥ 12 supports `ADD VALUE` in any transaction.)

### `mark_job_as_current` NULL fix (only for `module_type_id IS NULL`)

The current `mark_job_as_current` already handles `data_entry_type_id IS NULL` (lines
184-189). It does **not** handle `module_type_id IS NULL`. With Plan A's atomic
`claim_job`, the same NULL handling is needed there too. Plan A's `claim_job` is already
written with both NULL branches; this part of Plan B is a no-op once Plan A lands. (Listed
here for completeness; remove if Plan A and B ship in the same PR.)

### Endpoint change (`POST /sync/units` in `data_sync.py`)

```python
job = DataIngestionJob(
    job_type           = "unit_sync",
    module_type_id     = None,
    data_entry_type_id = None,
    year               = sync_request.target_year,
    ingestion_method   = IngestionMethod.api,
    target_type        = TargetType.REFERENCE_DATA,
    entity_type        = EntityType.GLOBAL_PER_YEAR,
    state              = IngestionState.NOT_STARTED,
    pipeline_id        = uuid4(),
    meta               = {"config": {"target_year": sync_request.target_year}},
)
created = await DataIngestionRepository(db).create_ingestion_job(job)
await db.commit()

asyncio.create_task(run_sync_task_accred(sync_request, created.id))
return SyncStatusResponse(
    job_id=created.id,
    state=IngestionState.NOT_STARTED,
    message="Unit sync scheduled",
)
```

### Task changes (`unit_sync_tasks.py`)

```python
async def run_sync_task_accred(
    sync_request: SyncUnitRequest,
    job_id: int,
) -> None:
    async with SessionLocal() as job_session, SessionLocal() as data_session:
        repo = DataIngestionRepository(job_session)
        if not await repo.claim_job(job_id, POD_ID):
            return

        try:
            # Existing fetch + upsert logic, with status_message updates between steps:
            #  - "Fetching units from Accred..."
            #  - "Upserting {N} units..."
            #  - "Creating carbon reports..."
            #  - "Ensuring modules..."
            ...
            await data_session.commit()
            await repo.update_ingestion_job(
                job_id, status_message="Unit sync completed", metadata=result_summary,
                state=IngestionState.FINISHED, result=IngestionResult.SUCCESS,
            )
            await job_session.commit()
        except Exception as exc:
            await data_session.rollback()
            await repo.update_ingestion_job(
                job_id, status_message=str(exc), metadata={},
                state=IngestionState.FINISHED, result=IngestionResult.ERROR,
            )
            await job_session.commit()
```

The `sync_units_from_accred_task` sync wrapper goes away — endpoint uses `asyncio.create_task`
directly (we are already in an async context).

---

## Part 6 — Rematch on recalc (Strategy A only)

### Why this is needed

Parts 2–4 close most of the FK-stability problem: upsert-in-place preserves `factor.id` when a
CSV re-uploads the same factor (same identity key) with new values. The recalc dereferences the
stable FK and reads the new values. Correct.

The hole is the **classification-change** case. The factor identity key includes
`classification`, so a CSV reupload that changes a factor's classification (supplier renamed,
vendor consolidated, sub-class added) does **not** update the existing row — it inserts a new
factor row, and the old row stays as stale (`last_seen_job_id` < latest). Existing
`DataEntry.primary_factor_id` continues to point at the stale row. The recalc job would then
read stale values via the stale FK and emit wrong numbers, silently.

This affects **Strategy A** entries only (equipment, purchases, process_emissions, etc. — see
`data_entry_emission_service._fetch_factors`, line 296). Strategy B entries (headcount,
travel, building) already re-match by classification at every recompute via
`factor_service.get_by_classification`, so they pick up the new factor automatically.

### Fix

In `EmissionRecalculationWorkflow.recalculate_for_data_entry_type`, before computing emissions
for each Strategy A data entry, re-resolve `primary_factor_id` against current factors. This
treats stored `primary_factor_id` as a cache and matching as the truth — within Plan B's
structure, no architectural reframe.

The canonical matching function already exists:
`ModuleHandlerService.resolve_primary_factor_id` (`module_handler_service.py:28`). Reuse it.

```python
# Inside EmissionRecalculationWorkflow, per data entry, before compute:
handler = get_handler(data_entry.data_entry_type)
if handler.kind_field is not None:           # Strategy A handlers expose kind_field
    refreshed = await module_handler_service.resolve_primary_factor_id(
        handler=handler,
        payload=data_entry.data,             # has kind/subkind classification fields
        data_entry_type_id=DataEntryTypeEnum(data_entry.data_entry_type),
        year=year,
        existing_data=None,
    )
    new_factor_id = refreshed.get("primary_factor_id")
    if new_factor_id != data_entry.primary_factor_id:
        data_entry.primary_factor_id = new_factor_id
        # data_session.add not strictly needed if data_entry already attached;
        # the dual-session pattern flushes on data_session.commit at end of task
```

After the loop, the existing `_fetch_factors` Strategy A path (`comp.factor_id = ...`) reads
the refreshed FK and computes against the correct factor.

### What this is **not**

- Not a switch to derived-only (Option A): we still cache `primary_factor_id` for read-time
  performance.
- Not full invalidation-and-relink at ingest time: the rematch happens during recalc, where we
  already iterate every affected entry. No extra query fan-out at ingest.
- Not a JSONB-classification change: that is Part 1, separate concern.

### Tests added (folded into the table below)

- Factor reupload that **changes classification** of an existing factor → existing
  Strategy A data_entries are re-linked to the new factor row; emissions reflect new values.
- Factor reupload that **only changes values** (same identity key) → existing
  `primary_factor_id` is unchanged (no churn), emissions reflect new values via stable FK.
- Strategy B entry → no `primary_factor_id` mutation needed (already derived).

---

## Tests

| Test                                        | Assertion                                                                             |
| ------------------------------------------- | ------------------------------------------------------------------------------------- |
| `upsert_factors` new row                    | factor inserted with id, last_seen_job_id stamped                                     |
| `upsert_factors` existing row               | values updated, **same id preserved**, last_seen_job_id updated                       |
| `upsert_factors` JSONB key order resilience | `{"a":1,"b":2}` and `{"b":2,"a":1}` resolve to same row                               |
| Stale factor query                          | factors not in latest job correctly returned                                          |
| `run_sync_task` FACTORS success             | one `emission_recalc` job per stale (module, det); each fired via asyncio.create_task |
| `run_sync_task` FACTORS ERROR               | no recalc jobs enqueued                                                               |
| `run_sync_task` DATA_ENTRIES (non-factor)   | no recalc jobs enqueued                                                               |
| `run_sync_task_accred`                      | NOT_STARTED → RUNNING (via claim_job) → FINISHED; status_message updates visible      |
| `run_sync_task_accred` claim guard          | mock claim_job → False, asserts task returns without API calls                        |
| `POST /sync/units`                          | returns real job_id (not 0); job is created, claimable                                |
| `claim_job` with `module_type_id IS NULL`   | unsets previous GLOBAL_PER_YEAR is_current correctly                                  |
| Recalc rematches on classification change   | Strategy A entries re-link to the new factor row; emissions use new values            |
| Recalc no-op on values-only change          | `primary_factor_id` unchanged when identity key matches; emissions reflect new values |
| Recalc Strategy B unaffected                | no `primary_factor_id` mutation; classification re-match happens in `_fetch_factors`  |

---

## Relevant files

- `backend/app/models/factor.py` — `Column(JSONB)`, `last_seen_job_id` field
- `backend/app/models/data_ingestion.py` — `EntityType.GLOBAL_PER_YEAR`
- `backend/app/repositories/factor_repo.py` — `upsert_factors`
- `backend/app/tasks/ingestion_tasks.py` — `_enqueue_stale_recalculations` at end of run_sync_task
- `backend/app/tasks/unit_sync_tasks.py` — `run_sync_task_accred` rewritten with claim + dual session
- `backend/app/api/v1/data_sync.py` — `POST /sync/units` returns real job_id
- `backend/app/api/v1/factors.py` — `GET /factors/stale?year=` (new)
- Factor CSV/API provider classes under `backend/app/providers/`
- `backend/migrations/` — JSONB conversion + unique index + last_seen_job_id + ALTER TYPE EntityType
