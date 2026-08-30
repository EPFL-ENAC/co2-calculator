---
status: in-progress
issue: 2295
last_updated: 2026-08-29
summary: "Exhaustive latency matrix for the table endpoint
  GET /v1/carbon-reports/{id}/modules/{module}/{sub}: every module ×
  submodule × limit {20,100,500,1000} × every sortable column × asc/desc,
  plus filter search, deep pagination, item GETs and the module chart
  companions, against a full-ceiling unit; sorted big pages folded into
  the concurrent ModuleReadUser ladder."
---

# Table pagination + sort matrix (#2295 follow-up)

**Goal:** find which (module, submodule, sort column, order, page size)
combinations exceed 1 s on the table endpoint that backs every module
table, e.g.
`/v1/carbon-reports/{id}/modules/equipment/it?page=2&limit=200&sort_by=id&sort_order=desc`.
The existing ladder only ever hit `page=1&limit=20` with the default sort.

## Facts the design hangs on (verified in code)

- The route caps `limit` at **1000** (`carbon_report_module.py:727`), so
  20/100/500/1000 are all legal.
- Sortable columns per submodule are **`handler.sort_map` keys** — every
  handler auto-registers in `MODULE_HANDLERS`
  (`app/schemas/data_entry.py:199`) — plus computed additions the repo
  layers on: `kg_co2eq` always; `room_surface_square_meter` (buildings);
  `distance_km`, `traveler_name`, `origin_name`, `destination_name`
  (travel) (`data_entry_repo.py:1292-1319`). The matrix must take columns
  from these two sources, not from a hand-written list.
- An unknown `sort_by` raises `ValueError` in `_apply_sort`
  (`data_entry_repo.py:685`) — the matrix asserts this surfaces as a 4xx,
  not a 500 (if 500: file a bug, that's user-triggerable).
- Track H's historic 825 ms production offender was exactly this endpoint
  family — this matrix is its systematic regression net.

## Data precondition

The current backdrop is scale 0.1 → biggest submodule holds ~500 rows.
For `limit=1000&page=2` to mean anything, one unit needs full-ceiling
density; the knobs already allow it:

```bash
SEED_CEILING_SCALE=1 SEED_CEILING_UNITS_PREFIX=U00000 \
  uv run -m app.seed.random_generator.seed_data_entries
```

(≈105k rows: 5 years × 21,050 for unit U00000 only, minutes.) Types whose
ceiling is 500 can never fill a 1000-row page — measure them at their real
maximum and say so in the report, don't inflate the data past #2161's
ceilings.

## Task 1 — matrix runner

`backend/tests/performance/table_matrix.py`, run as
`uv run python -m tests.performance.table_matrix --host http://127.0.0.1:8010`
(make target `perf-table-matrix`).

- Discover submodules from `MODULE_TYPE_TO_DATA_ENTRY_TYPES` (non-planner)
  and columns per the sources above.
- Auth: reuse `mint_auth_cookie` from the locustfile (principal of the
  full-ceiling unit) or `PERF_AUTH_COOKIE` for stage/dev.
- Iterate limit {20,100,500,1000} × order {asc,desc} × every column, at
  `page=2` (mirrors the reported URL; skips any first-page fast path).
  ~23 submodules × ~5-10 columns × 8 = **2-4k requests, sequential,
  ≈5-10 min**; `--repeat 3` knob records the median.
- Output: `reports/table_matrix.csv`
  (kind, submodule, column, order, limit, page, rows_returned,
  response_bytes, status, ms) + stdout table of combos over 1000 ms and
  over 400 ms (dev-platform proxy for 4 s), worst first.
  `report_slow.py` stays untouched — different shape.

### Added dimensions (same runner, extra axes)

- **`filter=` search** — the table's search box hits the same endpoint
  with a substring filter over name-ish JSONB fields; likely the least
  index-friendly path. One common 2-3 char probe per submodule × the four
  limits.
- **Deep pagination** — offset pagination degrades linearly; probe the
  LAST page (`page = ceil(count/limit)`) per submodule at limit 20 and
  100 (train at ceiling ≈ 5,500 rows → page ~275 is the worst realistic
  offset in the app today).
- **Single-item GET** — the row-expand path
  `/{report}/modules/{slug}/{sub}/{item_id}`: one probe per submodule
  (grab an id from the first page).
- **Module chart companions** — the module page renders
  `/{report}/modules/{slug}/stats-by-class` and
  `/{report}/modules/{slug}/top-class-breakdown` next to the table; one
  probe per module so a slow chart can't hide behind a fast table.
- **Payload size** — record response bytes per combo: a 1,000-row page
  can be megabytes, and serialization+transfer can dominate before the
  DB does; the CSV makes that visible.

## Task 2 — fold sorted big pages into the concurrent ladder

`ModuleReadUser.submodule_read` draws `limit` from {20,100,500,1000} and a
random valid sort column/order instead of fixed `page=1&limit=20`, so the
existing 50→1000 ladder exercises sorted pagination under concurrency. The
matrix (Task 1) finds the bad combos; the ladder shows how they behave
under load.

## Task 3 — run + report

Local (`:8010`, 4 workers) first; then stage with
`PERF_AUTH_COOKIE=<stage auth_token>` — reads only, safe, but coordinate
anyway. Post the offender table to PR #2526 / issue #2295.

## Out of scope (follow-ups, note in the report)

- `filter=` search latency matrix (same endpoint, separate axis).
- Deep pagination (`page` ≫ 2) — offset pagination degrades linearly;
  worth one probe at the last page of train (5000 rows).
- Planner submodules (`planner_*`) — planner ceilings unsized, same
  exclusion as the #2161 plan.
