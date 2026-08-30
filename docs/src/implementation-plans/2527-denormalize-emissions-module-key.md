---
status: in-progress
issue: 2527
last_updated: 2026-08-30
summary: "Denormalize the immutable join keys carbon_report_module_id and
  data_entry_type_id onto data_entry_emissions, plus a covering index
  (carbon_report_module_id, data_entry_type_id, data_entry_id) INCLUDE
  (kg_co2eq, emission_type_id, primary_factor_id, scope), so the kg_co2eq sort
  aggregate becomes one contiguous index range scan instead of a nested
  loop probing ~6 scattered pages per entry."
---

# Denormalize the module key onto `data_entry_emissions` (#2527)

**Goal:** make sorting a submodule table by CO₂ cost the same as sorting it
by any other column. Today it costs 5–7 s on the dev DB *regardless of page
size*.

**Scope:** the #2527 design comment ("Design for the kg_co2eq fix"),
validated with `EXPLAIN (ANALYZE, BUFFERS)` against the dev DB. Item 9 of
the #2527 top-10 list is superseded by this: the cost is not page size.

## Why this shape, and not "store kg_co2eq on the entry"

The guardrail is *don't store derived values in entries*. `kg_co2eq` is
derived — recalc owns it, it changes whenever a factor changes, and a copy
on `data_entries` would be a second source of truth that drifts silently.

`carbon_report_module_id` and `data_entry_type_id` are **not** derived.
They are immutable join keys: an entry's module and type are set at
construction and never change. Verified — no `update(DataEntry)`, no raw
`UPDATE data_entries`, and no re-parenting path anywhere in `backend/app/`
or `backend/alembic/`. Copying an immutable key onto the child row to give
the child its own access path is denormalization for locality, not a second
truth. `kg_co2eq` stays exactly where it is.

## Evidence (from the issue, dev DB, one purchases submodule)

| | Buffers | Disk reads (warm) |
|---|---:|---:|
| Today: nested loop over `ix_data_entry_emissions_data_entry_id` | ~37,400 pages for 6,000 rows (≈6 scattered pages/row) | 1,770 |
| With the covering index: one contiguous range scan, index-only | tens of pages | ~0 |

Warm, the aggregate alone is 214 ms; cold on shared storage it is the
measured 5–7 s endpoint. Matrix baseline: 184 `kg_co2eq` combos, median
829 ms, max 9.9 s, flat across `limit` ∈ {20, 100, 500, 1000}.

**Bonus, same migration:** the entries side BitmapAnds
`ix_data_entries_carbon_report_module_id` with
`ix_data_entries_data_entry_type_id` (module scan alone: 46.8k rows / 953
reads). `uq_member_role_per_module` looks like a composite but is partial
(`WHERE data_entry_type_id = 1`), so it cannot serve the general case. A
plain composite `(carbon_report_module_id, data_entry_type_id)` on
`data_entries` is a cheap add-on.

---

## Phase 1 — schema, write paths, and the four hot query sites

### T1. Model columns and indexes (declared in model code, never hand-written)

`backend/app/models/data_entry_emission.py`, on `DataEntryEmissionBase`:

- `carbon_report_module_id: int` — nullable in the model *only if* T3's
  answer says the `SET NOT NULL` must be deferred (see the open question);
  otherwise `nullable=False`.
- `data_entry_type_id: int` — same.

No `ForeignKey` on `carbon_report_module_id`. Deletion already cascades
through `data_entries.id`, and an FK adds a per-row constraint check on the
`COPY … FROM STDIN` hot path that recalc runs millions of times. The
column is a copy of an already-FK'd value, not a new reference.

`index=True` cannot express `INCLUDE`, so the covering index goes in
`__table_args__` — this is what makes `make db-revision` emit the DDL
instead of someone hand-authoring it:

```python
__table_args__ = (
    Index(
        "ix_dee_module_type_entry",
        "carbon_report_module_id",
        "data_entry_type_id",
        "data_entry_id",
        postgresql_include=[
            "kg_co2eq", "emission_type_id", "primary_factor_id", "scope",
        ],
    ),
)
```

`scope` is in `INCLUDE` beyond the design comment's three columns: the
buildings and headcount rollup joins filter on `scope IS NULL`, and without
it Postgres visits the heap for every row surviving the `emission_type_id`
filter just to evaluate that predicate. It is a nullable int — nearly free
in the index, and it is what keeps those two branches index-only.

Same treatment for the bonus, in `backend/app/models/data_entry.py`:

```python
Index("ix_data_entries_module_type", "carbon_report_module_id", "data_entry_type_id")
```

Keep `ix_data_entry_emissions_data_entry_id`. `delete_by_data_entry_ids`,
`get_by_data_entry_id` and `delete_by_data_entry_id` all drive on
`data_entry_id` alone and would otherwise lose their access path.

Add both indexes to `backend/alembic/CUSTOM_DB_OBJECTS.md` under
"Captured in models — verify, don't hand-write", so a future collapse
confirms they survived.

### T2. `DataEntryEmissionRow` carries the keys, stamped once

`DataEntryEmissionRow` (same file) gains the two fields as
`int | None = None`. **Not `0`** — a defaulted-away key writes a row into
module 0 that then silently vanishes from every new aggregate. That is the
silent fallback this whole design exists to avoid.

`prepare_create` (`data_entry_emission_service.py:388`) already receives a
`DataEntry | DataEntryResponse`, and `DataEntryResponse` extends
`DataEntryBase`, so both keys are always in hand. Stamp them **once, over
`results`, right before the return** rather than editing the four
`DataEntryEmissionRow(...)` sites (lines ~619, ~649, ~707, ~739) — three
lines instead of eight edits, and structurally impossible for a future
fifth construction site to miss.

`to_orm()` copies both fields and raises when either is `None`. That single
guard covers `create`, `bulk_create`, `upsert_by_data_entry`, and
`bulk_copy`'s non-psycopg (SQLite/asyncpg test) fallback.

### T3. Every write path

All application emission writes funnel through `prepare_create` →
`DataEntryEmissionRow` → either `bulk_copy` (psycopg COPY) or `to_orm()` +
`bulk_create`. Verified callers: `EmissionRecalculationWorkflow`,
`SimulatorPlanService._prepare_plan_emissions`, `base_csv_provider`,
`workflows/carbon_report_module.py` (`create`, `upsert_by_data_entry`).
Two files need edits, plus one standalone seeder:

1. **`repositories/data_entry_emission_repo.py`** — `_EMISSION_COPY_SQL`
   gains `carbon_report_module_id, data_entry_type_id`, and `bulk_copy`'s
   `copy.write_row(...)` tuple gains the two values **in the same
   positional order**. COPY is positional: a column-list/tuple mismatch
   here mis-assigns silently. Raise in the write loop when either is
   `None`.
2. **`models/data_entry_emission.py`** — `to_orm()` (T2).
3. **`seed/random_generator/seed_data_entries.py`** — the raw-asyncpg
   `copy_insert_emissions` is a separate write path that bypasses the ORM
   entirely. Three edits: the `tmp_emissions` temp-table DDL, the
   `INSERT INTO data_entry_emissions (…)` column list, and
   `generate_emissions_for_entry(entry_id, data_entry_type_id)` — which
   must also take `carbon_report_module_id`, threaded from the batch loop
   (`module["id"]` is already in scope at the `copy_insert_emissions`
   call site).

### T4. Migration (generated, then pruned)

`cd backend && make db-revision message="denormalize module key onto data entry emissions"`,
then prune the false-positive `drop_index` calls autogenerate emits. The
DB persists across deploys, so the backfill is **required** — this is not a
"moot after reseed" migration.

Order inside `upgrade()`:

1. `add_column` × 2, **nullable** (autogenerated).
2. Backfill:
   ```sql
   UPDATE data_entry_emissions dee
   SET carbon_report_module_id = de.carbon_report_module_id,
       data_entry_type_id      = de.data_entry_type_id
   FROM data_entries de
   WHERE de.id = dee.data_entry_id
     AND dee.carbon_report_module_id IS NULL
   ```
   ~700k rows on the shared environments. Batch by `dee.id` range
   (`AND dee.id BETWEEN :lo AND :hi`, 100k-row chunks) so no single
   statement holds row locks over the whole table. The `IS NULL` predicate
   makes it re-runnable. It writes only `data_entry_emissions`, so the
   `updated_at`-staleness warning in `CUSTOM_DB_OBJECTS.md` (which concerns
   raw `UPDATE data_entries`) does not apply; do **not** touch
   `computed_at` — it records when the emission was computed, not when the
   row was rewritten.
3. `alter_column(… nullable=False)` × 2 — **subject to the open question
   below.**
4. `create_index` × 2, **after** the backfill (indexing a column that is
   about to be fully rewritten is wasted work).

`CREATE INDEX CONCURRENTLY` cannot run inside Alembic's transaction.
Proposal: accept the blocking `CREATE INDEX` — the covering index on
`data_entry_emissions` is the expensive one, and the deploy already runs
migrations as a gated Job before traffic. If the maintainer wants zero
write-blocking, it splits into a follow-up migration with
`autocommit_block()`.

### T5. Query rewrites — `repositories/data_entry_repo.py`

**The trap:** `module_entry_ids` (line ~1000) does *two* jobs — the module/
type scope, and the #2404 page-first narrowing (`DataEntry.id IN
page_entry_ids`). For `kg_co2eq` sorts `_page_first_eligible` returns
`False`, `page_entry_ids is None`, and the aggregate spans the whole module
— that is the 37,400-page problem. For every *other* sort, `page_entry_ids`
is a ~20-id list and the aggregate is already cheap.

So the rewrite must **keep** the page narrowing, not replace it:

```
dee.carbon_report_module_id = :module_id
AND dee.data_entry_type_id  = :type_id
AND dee.data_entry_id = ANY(:page_entry_ids)   -- only when page-first applied
```

`data_entry_id` is the index's third column, so both shapes ride
`ix_dee_module_type_entry`. Dropping the narrowing would make the majority
of the 1,519 matrix combos *slower*. Delete `module_entry_ids` itself
(the `IN`-subquery over `data_entries`); it has no remaining job.

All three `kg_sort_expr` branches:

| Branch | Site | Change |
|---|---|---|
| Buildings | `building_emission_agg_q`, ~L1022 | replace `.where(data_entry_id.in_(module_entry_ids))` with the two column predicates + the optional `page_entry_ids` narrowing. **Also** add the two predicates to the `RollupEmission` outer-join ON clause so the rollup probe uses the covering index too — its `scope IS NULL` filter is why `scope` is in `INCLUDE`. |
| Headcount | `RollupEmission` join, ~L1084 | no subquery to rewrite; add the two predicates to the join ON clause (same `scope IS NULL` note as above). `kg_sort_expr` stays `RollupEmission.kg_co2eq`. Mirror the same predicates into `count_factor_joins`, which must join identically or the count degenerates. |
| Generic / travel | `emission_agg_q`, ~L1133 | same rewrite as buildings. |

Update the `#2050 J8` comment in place: the restriction it describes is now
enforced by the emissions row's own columns, not by an entry-ids subquery.

Fourth site, same file: **`get_professional_travel_trip_legs`** (~L1549) —
its `module_entry_ids` filters on module only (no type), so it becomes
`dee.carbon_report_module_id = :module_id`. Its own comment (the subquery
"runs twice in the mode loop") stops being a caveat.

**Explicitly out of scope:** `_reference_kg_by_source_ids` (~L1520). It is
keyed on an arbitrary set of planner source entry ids with no module
filter; the new key buys it nothing. Leave it alone.

### T6. Tests

- **Regression (the one that catches a desync):** assert the denormalized
  aggregate returns totals identical to the `DataEntry`-join version on a
  seeded module — for all three branches. Mirror the harness in
  `backend/tests/integration/services/data_ingestion/test_submodule_get_scaling_pg.py`;
  do not invent a new one.
- **Write-path coverage:** one test per path proving the columns land —
  recalc (`bulk_copy`, psycopg), single-entry (`upsert_by_data_entry`,
  `to_orm`), and the `to_orm()` guard raising on an unstamped row.
- **~44 direct `DataEntryEmission(...)` constructions across ~14 test
  files** will fail the new `NOT NULL`. Add a `make_emission(entry, **kw)`
  factory to `backend/tests/conftest.py` that derives both keys from the
  entry, and route the call sites through it — one helper instead of 44
  hand-edits, and the next test cannot forget.

### T7. Acceptance gate

`make perf-table-matrix PERF_HOST=…` against the dev DB — **run by the
maintainer**, not from an agent session (the perf README notes background
children die with the session, and long sweeps belong in a real terminal).

| Metric | Before | Target |
|---|---|---|
| `kg_co2eq` combos over 1 s | 184 | 0 |
| `kg_co2eq` median | 829 ms | < 200 ms |
| `kg_co2eq` max | 9.9 s | < 1 s |
| Non-`kg_co2eq` combos | matrix baseline | **no regression** — proves T5 kept the page narrowing |

That last row is the one that catches the trap in T5.

---

## Phase 2 — the stats aggregations this also unlocks (enumerated, not in this PR)

Every one of these joins `DataEntry` *solely* to reach
`carbon_report_module_id`. Splitting them honestly:

**Lose the `DataEntry` join entirely** (`repositories/data_entry_emission_repo.py`):

- `get_stats_pair_many` — the merged modules-stats trio (#2527 item 4) reads
  through this.
- `get_stats_pair`

**Lose one join** — `get_validated_totals_by_unit` can join
`CarbonReportModule` directly on `dee.carbon_report_module_id`, dropping
`DataEntry` from a four-table chain. Feeds `unit_totals_service`.

**Keep `DataEntry`** (they need `data` / `source` / `data_entry_type_id`
from the entry itself) **but get a better driving scan** —
`get_stats`, `get_travel_stats_by_class`, `get_top_class_breakdown`,
`get_embodied_energy_by_building`, `get_embodied_energy_by_category`.

Phase 2 is deliberately separate so the Phase 1 perf number is bisectable:
if the matrix does not move, the cause is in Phase 1's four sites and
nowhere else.

---

## Open question for the maintainer

**Can `SET NOT NULL` ship in the same migration, or must it be a
follow-up?**

`additive nullable → backfill → NOT NULL` is only safe if the migration Job
completes and old pods are fully drained before anything inserts again.
During a rolling deploy, an old-code pod inserting an emission row after
`SET NOT NULL` fails the constraint — and this repo has already been burned
by migration-Job ordering (PR #1775).

- **If the deploy guarantees migration-Job-completes-then-new-pods:** one
  migration, `NOT NULL` included, as written in T4.
- **If not:** two migrations — this PR ships nullable columns + backfill +
  indexes, and a follow-up adds `SET NOT NULL` once the write-path code is
  live everywhere. The `to_orm()` / `bulk_copy` raises from T2–T3 hold the
  invariant in application code in the meantime.

The answer changes the migration count and T1's `nullable=` values. It is
the only thing blocking implementation.
