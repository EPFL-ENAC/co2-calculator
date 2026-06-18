# Copilot review triage — PR #1346 (issue #282, trips map)

Source: `copilot-pull-request-reviewer[bot]` review on PR #1346 (fetched via public
GitHub API; `gh` auth was unavailable).

## Raw Feedback

1. **frontend/src/utils/trips-map.ts:57** — Direction normalisation uses lexicographic
   string comparison of coordinates, which is not a stable numeric ordering (e.g.
   "10,0" < "2,0"). Claims this can fail to collapse A→B and B→A, producing duplicate
   routes.
2. **frontend/src/stores/modules.ts:822** — Trips-map fetch/caching ignores
   `carbon_project_type`; other module endpoints include it. Without it the map can show
   the wrong dataset and the cache key can reuse results across calculator/simulator.
3. **docker-compose.yml:49** — Postgres volume mounted at `/var/lib/postgresql` instead
   of `/var/lib/postgresql/data`; claims this breaks persistence.
4. **backend/app/repositories/data_entry_repo.py:842** — `limit(max_rows)` is applied
   separately for plane and train, so the method can return up to ~2×max_rows rows.
5. **backend/app/repositories/data_entry_repo.py:828** — Location join conditions bypass
   the project's usual `col(...)` wrapping used elsewhere in the query.
6. **backend/app/repositories/data_entry_repo.py:859** — `number_of_trips` defaults to 1
   when `n_trips` is falsy, also turning a stored 0 into 1.
7. **backend/tests/integration/v1/test_professional_travel_trips_map.py:96** — Service
   mock returns a `MagicMock` with a `model_dump()` method; depends on FastAPI internals
   and can break `response_model` validation. Prefer a plain dict / `TripsMapResponse`.
8. **frontend/src/components/molecules/TripsMap.vue:8** — Wrapper is `role="img"` but the
   embedded MapLibre canvas is interactive; prefer `role="region"` (or no role).

---

## Action Items

### Critical: logic, security, correctness

- [ ] **frontend/src/stores/modules.ts** (#2, valid) — `getProfessionalTravelTripsMap`
      omits `carbon_project_type`, yet the backend route (`carbon_report_module.py:581/596`)
      resolves the report type from it (default `0` = Calculator). So the map always renders
      Calculator data, and the cache key `${unit}|${year}` reuses it when switching to
      Simulator. Fix: send `searchParams: { carbon_project_type: carbonProjectType.value }`
      on the `api.get`, and add `carbonProjectType.value` to `cacheKey` (mirror the pattern at
      modules.ts:406/433).

### Correctness (minor / edge cases)

- [ ] **backend/app/repositories/data_entry_repo.py** (#4, valid) — `statement.limit(max_rows)`
      is inside the plane/train loop, so the cap is per-mode and the method can return up to
      2×`max_rows`. Fix: track a remaining budget `max_rows - (len(legs) + dropped)` and limit
      the second query to it (break early if ≤ 0). Low severity — it's a safety cap on a viz
      endpoint, not user-facing.
- [ ] **backend/app/repositories/data_entry_repo.py:858** (#6, valid) — `int(n_trips) if
n_trips else 1` turns a stored `0` (and `None`) into `1`. Fix: `int(n_trips) if n_trips
is not None else 1` to preserve `0`.
- [ ] **frontend/src/components/molecules/TripsMap.vue:8** (#8, valid) — `role="img"` on a
      pan/zoom MapLibre canvas misrepresents it to assistive tech. Fix: change the wrapper to
      `role="region"` (keep `aria-label`); the existing `sr-only` leg list still provides the
      text alternative.

### Maintainability (optional, low priority)

- [ ] **backend/app/repositories/data_entry_repo.py:820-826** (#5, partial) — Location join
      conditions don't use `col(...)` like the rest of the query. CI mypy is green, so this is
      consistency-only; wrap them if you want uniformity, otherwise skip.
- [ ] **backend/tests/integration/v1/test_professional_travel_trips_map.py:96** (#7, valid) —
      Replace the `MagicMock`-with-`model_dump()` service stub with a plain dict or a real
      `TripsMapResponse` so the test doesn't lean on FastAPI's arbitrary-object handling.

### Dropped (verified false / stale)

- **#1 trips-map.ts:57** — WRONG. Lexicographic string comparison is still a _consistent
  total order_, so for any pair {A,B} both input directions canonicalise to the same
  `(from,to)` and collapse into one bucket. It only affects which endpoint is labelled
  "from" — cosmetic, and the popup shows `from ↔ to` anyway. No dedup bug.
- **#3 docker-compose.yml:49** — WRONG/stale. Image is `postgres:18-alpine`; PG18 changed
  the default `PGDATA` and moved the declared `VOLUME` to `/var/lib/postgresql`, so the
  current mount is correct for 18 — reverting to `/data` would break it. (Also unrelated to
  this feature; it came from commit `ac8a0127`.)
