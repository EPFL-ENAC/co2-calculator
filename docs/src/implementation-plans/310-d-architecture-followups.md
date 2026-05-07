---
status: planned
issue: 310-d
last_updated: 2026-05-07
title: "310-d Architecture Follow-ups (post-PR1054)"
summary: "Three load-bearing concerns surfaced during the PR #1054 architecture review: pipeline-failure observability, dedup_active generalisation, and unified pipeline-state store."
---

# 310-d Architecture Follow-ups

## Context

After PR #1054 (frontend stale-stats UX + back-office Recalculating
badge) merged on 2026-05-07, a hard-look review of the 310-D series
surfaced three structural concerns that the individual PRs each
patched around without addressing the underlying architecture. This
plan stages each as a focused follow-up so they can be sequenced
deliberately rather than absorbed ad-hoc into the next ticket.

The three are independent and can land in any order. None are
blockers for current 310-D functionality; each is a "shape of the
codebase" investment.

---

## Follow-up 1 — Pipeline-failure observability backstop

### Problem

The runner-driven chain
`csv_ingest → emission_recalc → aggregation` is correct end-to-end
and surfaces failures via:

- Job state writes (`update_ingestion_job(state=FINISHED,
result=ERROR, status_message=str(exc))`) — visible to the dashboard
- The frontend "Last recalc failed" badge (PR #1054)
- Structured logs (with the IntegrityError race-loss INFO line from
  PR #1053)

These cover the **interactive** case: an operator who's looking at
the back-office page sees the badge, opens devtools, follows the
exception. But they don't cover the **passive-observation** case:

- Background failures with no operator watching at the time
- Stuck NOT_STARTED rows the safety poller never picks up (e.g., a
  schema change broke `_pending_runner_jobs_query`)
- Slow-burn drift where the chain succeeds but the data ends up
  inconsistent with the source CSVs

There's no SINGLE place that owns the contract "data committed
implies emissions will be computed AND surfaced". A regression in
any link breaks the contract silently for non-interactive users.

### Proposal

Add a backend health-probe endpoint that surfaces stale-stats older
than threshold X:

```
GET /v1/sync/health/stale-stats?older_than_minutes=60
→ [{module_type_id, year, last_finished_aggregation_at, why_stale}]
```

Backed by a SQL query that joins:

- `carbon_report_modules` (the source-of-truth modules)
- `data_ingestion_jobs` filtered to `job_type = 'aggregation'`
  and `state = FINISHED`, latest per `(module_type_id, year)`
- Compares `finished_at` against the threshold

Results expose:

- `why_stale`: enum of `no_aggregation_ever`, `last_aggregation_failed`,
  `last_aggregation_too_old`, `pending_aggregation_stuck`
- The relevant `data_ingestion_job.id` for the operator to drill in

Optional consumers:

- Datadog/Prometheus scrape (most valuable — passive monitoring)
- Admin /health page in the frontend (low value vs. the per-module badge)
- A k8s liveness probe variant (overkill — false positives on slow chains)

### Out of scope

- Auto-retry for failed pipelines (a real product decision; see
  Follow-up 1.5 below if pursued)
- Alerting infrastructure (Datadog rules, Slack hooks) — left to
  whoever wires the scrape

### Sub-question worth deciding before implementing

Should chain failures auto-retry server-side, or stay
operator-triggered? The plan above assumes operator-triggered (with
the badge as the signal). If auto-retry is the product call, the
backstop can also schedule a retry job when `why_stale` indicates
a recoverable failure — but that's a separate behavior change with
its own failure mode (retry storms on broken handlers). Discuss
before committing.

### Estimated cost

- Backend endpoint + SQL: ~half a day
- Tests: ~2h (PG integration covering the four why_stale variants)
- Plumbing into Datadog/Prometheus: ~1 day depending on the existing
  scrape infra
- **Total: ~2 days** with the optional plumbing

---

## Follow-up 2 — Generalise `chain_job(dedup_active=True)`

### Problem

`chain_job(dedup_active=True)` is documented as a generic
"opt-in dedup" mechanism for any job type with a matching partial
unique index. The implementation in
`backend/app/tasks/_chain.py::_insert_child_with_dedup` is NOT
generic — it hard-codes `job_type = 'aggregation'` in two places:

1. The pre-check `SELECT 1 ... WHERE job_type = 'aggregation' ...`
2. Implicit reliance on the `uq_aggregation_active` partial unique
   index

PR #1053 fixed the docstrings to acknowledge the gap (alignment is
honest now), but the wrong-shape API survives. The next dedupable
handler will either:

- Copy-paste `_insert_child_with_dedup` and rename the constants
  → drift over time
- Refactor on the fly when adding the second consumer → adds scope
  to whatever feature actually needed dedup

Either path is worse than parameterising now.

### Proposal

Refactor the pre-check + INSERT to take a `DedupConfig`:

```python
@dataclass(frozen=True)
class DedupConfig:
    job_type: str           # filter for the pre-check + the INSERT row
    scope_columns: tuple[str, ...]  # columns the partial unique index keys on
    constraint_name: str    # for IntegrityError diagnostic logging
```

Built-in registration for known dedupable types:

```python
AGGREGATION_DEDUP = DedupConfig(
    job_type='aggregation',
    scope_columns=('module_type_id', 'year'),
    constraint_name='uq_aggregation_active',
)
```

`chain_job` accepts `dedup_config: Optional[DedupConfig] = None`
instead of `dedup_active: bool = False`. Existing callers migrate
to `dedup_config=AGGREGATION_DEDUP`; new callers register their own.
The SQL is built dynamically from `scope_columns` (tuple → IN clause

- NULL handling for each).

### When to do this

Trigger condition: **the moment a second dedupable handler is on
the horizon**. Doing it pre-emptively risks YAGNI. Doing it
reactively risks the second consumer copying the existing shape
before refactoring. Pre-condition the work on a concrete second
use case (the most likely candidate today is a "progress-bar
refresh" job per the PR #1053 plan note).

### Out of scope

- Migrating existing aggregation index to a generic naming scheme
  (it's already named for aggregation; keep)
- Cross-table dedup (the current shape only works for
  `data_ingestion_jobs`)

### Estimated cost

- Refactor + tests: ~half a day
- **Total: ~half a day** when triggered

---

## Follow-up 3 — Unified `pipelineStateStore` (the highest-leverage one)

### Problem

After PR #1054, the frontend tracks the same backend state from two
different stores via two different endpoints:

| Store                                                         | Field                          | Source endpoint                     | Consumer pages |
| ------------------------------------------------------------- | ------------------------------ | ----------------------------------- | -------------- |
| `useTimelineStore.currentPipelineIds`                         | per-`Module`-enum              | `GET /carbon-reports/{id}/modules/` | report views   |
| `yearConfigStore.recalculationStatus[id].current_pipeline_id` | per-`module_type_id` (numeric) | `GET /year-configurations/{year}`   | back-office    |

Two views of the same backend state, with different keys, populated
by two different store actions, kept in sync only by the contract
that backend handlers update both source endpoints' underlying tables
atomically.

This works **today** because no page consumes both stores. The
moment a future page wants both views (e.g., a dashboard that mixes
report-style stats with back-office-style admin actions), the two
sources can disagree mid-fetch. And the duplication taxes every
future change: adding a new field (e.g., `pipeline_started_at`)
requires updating both schemas, both endpoints, both store
populators.

### Proposal

Introduce `frontend/src/stores/pipelineState.ts`:

```typescript
export interface PipelineStateEntry {
  pipeline_id: string;          // the active pipeline_id, or null
  module_type_id: number;
  year: number;
  fetched_at: number;           // for staleness tracking
}

export const usePipelineStateStore = defineStore('pipelineState', () => {
  // Keyed by `${module_type_id}:${year}` (string keys are the only
  // way Pinia composite-keyed maps stay reactive without weakmap
  // gymnastics).
  const entries = reactive<Record<string, PipelineStateEntry>>({});
  ...
});
```

One backend endpoint backs it (already shipped — the bulk
`get_current_pipeline_ids_for_modules` repo helper from PR #1053):

```
GET /v1/sync/active-pipelines?year=Y&modules=1,2,3
→ {1: "uuid-1", 2: null, 3: "uuid-3"}
```

Both `useTimelineStore` and `yearConfigStore` keep their existing
responsibilities (timeline status display, year config) but DROP the
`current_pipeline_id` field. Their populators stop tracking it; the
new store becomes the single source. Consumers (today: only
`ModuleConfig.vue` from PR #1054) read from the new store.

The new endpoint is a thin wrapper over the existing repo helper:

```python
@router.get("/active-pipelines", response_model=dict[int, Optional[UUID]])
async def active_pipelines(year: int, modules: list[int] = Query()) -> dict[int, Optional[UUID]]:
    repo = DataIngestionRepository(db)
    return await repo.get_current_pipeline_ids_for_modules(modules, year)
```

### Why this is the highest-leverage of the three

- **Eliminates the dual-source-of-truth class entirely** — not just
  papered over with documentation.
- **Reduces future field-addition cost** — one schema, one populator,
  one consumer surface.
- **Makes the pipeline state cacheable / SSE-pushable** independently
  of the carbon-report or year-config request lifecycle.

### When to do this

Trigger: any of:

- A third consumer page wants per-module pipeline state
- A new field gets added to the pipeline state (e.g., `started_at`,
  `current_step`, `progress_percent`) and the cost of updating both
  schemas becomes visible
- After the 310-D series stabilises and the frontend stack has time
  for an invasive but contained refactor

Pre-condition: the existing badge UX is stable and well-tested in
its current form. Don't refactor stores while the consuming
component is also evolving.

### Out of scope

- A "pipeline detail" page showing the full job list (this plan only
  refactors state plumbing, not adding new UX surfaces)
- Auto-subscription via SSE on the store level (the
  `usePipelineStream` composable from PR #1054 stays as-is)

### Estimated cost

- Backend endpoint + tests: ~2h
- New store + composable update: ~3h
- Migration of existing consumer (`ModuleConfig.vue`): ~1h
- Removal of `current_pipeline_id` from the two existing stores: ~1h
  (minor — the field is `?` so removal is non-breaking)
- **Total: ~1 day**

---

## Sequencing recommendation

1. **Follow-up 3 first** if any of its trigger conditions hits (most
   likely first, given the dual-source taxes future changes).
2. **Follow-up 1** when passive monitoring becomes a product priority
   (no urgency today; the badge handles interactive observation).
3. **Follow-up 2** ONLY when a second dedupable handler is being
   added. Don't do it pre-emptively.

---

## Tests

Each follow-up ships with its own test surface; this plan doesn't
need integration tests since it's docs only.

---

## Out of scope for this plan

- Component-integration follow-ups for the existing badge (button
  transformation, popover/tooltip) — those are tracked in the
  immediate PR queue, not as architecture.
- Bulk-path provider emission-write removal — already shipped in
  PR #1053.
- Strategy B rematch — already shipped in PR #1042.

---

## Open questions

- **For Follow-up 1**: auto-retry vs operator-triggered? Surfaces a
  product call about UX recovery semantics.
- **For Follow-up 2**: is the "progress-bar refresh" job actually a
  thing we want to build, or speculative? If speculative, defer.
- **For Follow-up 3**: should the new store also own the
  `usePipelineStream` lifecycle (auto-subscribe on entry, auto-close
  on entry expiry)? Tighter coupling but cleaner consumer API.
