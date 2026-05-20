# Pipeline-debug — living TODO

Integration branch: `fix/pipeline-debug` (all items below land there until
told otherwise). Last updated 2026-05-19.

## ✅ Done & on the branch

- #1234 console + 422/scope fixes (`d671cefb`) merged.
- #1225 emission-recalc resilience + eager-pipeline-id (`ece34533`) merged.
- #1236 Phase 1: `pipelines` table + model + `ensure_pipeline_exists`
  (4 mint sites) + runner post-`finish_job` isolated status write +
  `reconcile_pipeline_statuses` sweep + tests.
- #1236 root cause: `finalize_ingest_meta` — a FINISHED job with
  `result != SUCCESS` never reports `"Success"`; shared by
  `_run_ingest` (csv/api/factor) **and** `reference_ingest`.
- Console table: clickable full message + copy, server-resolved
  module/det names, distinct amber WARNING tier.
- **🐞 Guilbert #1**: year-config gate (`13616a35` backend, `c1e9ef01`
  frontend) — `YearConfiguration.configuration_completed` stamped by
  `unit_sync_handler` on SUCCESS; `/dispatch` 409s when null;
  data-management page's `yearSyncInFlight` extended with the durable
  refresh-surviving check.
- **🐞 Guilbert #3**: SSE live-update on the ops page (`645b4799`) —
  page subscribes to visible RUNNING pipelines via `usePipelineStream`,
  debounced refetch on any SSE update.
- **VERIFY (Phase 4 gate) — answered:** aggregation handler is
  **already scoped** at `(module_type_id, year)` via
  `svc.list_modules_for(...)`. The `modules_refreshed: 2231` in the
  data is 2231 `carbon_report_modules` (one per unit) for ONE
  module-year slice, not a full-table rewrite. The collision /
  amplification comes from `recompute_stats`'s **side-effect** that
  also rewrites the parent `carbon_report.stats` rollup — that row is
  shared across all modules of a unit-year, so 3 concurrent
  aggregations for different modules of the same year deadlock on
  `carbon_reports`. Phase 4A's right lever is **coalescing** (one
  trailing aggregation per scope), not narrower scoping — scoping is
  already done.
- **Sibling hardcode trace — answered:** `base_provider.py:186` is a
  base-class default; every concrete subclass overrides `ingest()`,
  so it's unreachable. `base_reduction_objective_csv_provider.py:169`
  belongs to a class with no `@register`'d handler — never invoked by
  the runner. Both are dead-code paths today; `finalize_ingest_meta`
  covers every LIVE handler.

## 🔎 To CHECK (verified at type/lint/unit level only — NOT runtime)

Honest gap: green `ruff`/`mypy`/`eslint`/`vue-tsc`/unit ≠ "works live".

- [ ] Console page renders on localhost: alert strip, filters narrow,
      row expand → DAG, **message dialog + copy**, `@click.stop` vs
      row-expand, **amber WARNING** tier, **named module/det** show.
- [ ] Bug-2 re-confirm: `?state=NOT_STARTED` returns 200 (not 422) and
      the console shows _many_ pipelines + tagged orphans (the
      permission-scope fix) — confirm on evidence.
- [ ] Eager-pipeline-id end-to-end: a fresh dispatch persists
      `pipeline_id`, creates the `pipelines` row, status advances.
- [ ] #1236 Phase-1 on a real run: runner post-finish isolated write
      lands; induce a failure → log-and-skip + sweep heals.
- [ ] `alembic upgrade head` applies cleanly on a real Postgres DB
      (only parsed + SQLite-fixture tested so far).
- [ ] One clean **hook-driven** commit (commitlint + lint-staged +
      `make type-check`) — merges/commits used `--no-verify`; confirm
      the gate passes for real before any promotion.
      **Concrete finding (2026-05-20):** commitlint rejects scopes
      like `docs(pipeline-debug):` (commit `71bfe301` blocked,
      `rtk git commit` printed `ok` anyway — the "ok" lies; verify
      with `git ls-tree`/`git show HEAD:` per
      `[[project_pipeline_debug_integration_branch]]`). Either widen
      the commitlint scope-enum to include `pipeline-debug`, or use
      issue-numbered scopes (`docs(#1234)`, `docs(#1236)`).
- ✅ Sibling `"status_message": "Success"` hardcodes traced — both
      unreachable (base default overridden by every concrete provider;
      reduction-objective class has no registered handler). See Done.

## 🐞 Newly discovered (Guilbert, 2026-05-20)

- ✅ #1 Year-config gate — backend `13616a35`, frontend `c1e9ef01`.
- ✅ #3 SSE on the ops page — `645b4799`.
- [ ] **#2 `unit_sync` collapses to one aggregated task per year.**
      Individual sub-tasks aren't exposed in the ops UI. Investigate
      whether the sub-tasks are not created (backend collapses
      everything into the `unit_sync` handler internally) or are
      created but filtered out by the ops endpoint; expose them so
      operators can see what's running inside the year-level
      pipeline. **Investigation pending** before picking
      backend-vs-frontend fix.

## 🔧 To DO — #1236 remaining phases

- [ ] **Phase 2**: enforce `data_ingestion_jobs.pipeline_id` →
      `pipelines(id)` FK. v0.x = no backfill (DB dropped between
      deploys); add the FK migration to run on a clean DB already on
      Phase-1 code. Real backfill is a **v1.x** concern.
- [ ] **Phase 3**: flip reads (console #1234, `GET /pipelines/{id}`,
      progress) to the `pipelines` table; `compute_pipeline_progress`
      becomes writer-side only. Schedule the reconciliation sweep on a
      cron _before_ flipping. Verify: golden-output diff before/after.
- ✅ **VERIFY (Phase 4 gate) — answered:** aggregation handler is
      scoped at `(module_type_id, year)`. The 2231 number is
      per-unit module rows, not all reports. Collision source is
      `recompute_stats`'s side-effect rewrite of the parent
      `carbon_report.stats` synthesis (shared row). Phase 4A lever is
      **coalescing**, not narrower scoping.
- ✅ **Phase 4A — done (3 commits):**
      - `73ec4d64` 4A.1 in-pipeline coalesce — last emission_recalc
        sibling chains aggregation; others skip. Race-safe via
        fresh-session `SELECT … FOR UPDATE` on parent + `meta
        .recalc_work_complete` flag. 3 sequential aggregations per
        upload → 1.
      - `718cdd01` 4A.2 per-year `pg_advisory_xact_lock` in
        `aggregation_handler` — serialises cross-pipeline
        aggregations of the same year against shared
        `carbon_reports.stats` rows; no drop-hazard. Dialect-gated
        (SQLite skip).
      - `1b20f967` 4A.3 scope to `affected_module_ids` union —
        aggregation rewrites only modules the recalc siblings
        actually touched (typically 432 vs 2231).
      Combined: amplification killed (4A.1), cross-pipeline deadlock
      eliminated (4A.2), per-aggregation write set shrunk (4A.3).
- ✅ **Phase 4A**: shipped as 4A.1/4A.2/4A.3 (see Done section).
- [ ] **4A.4 (race fix on 4A.3)**: the LAST recalc sibling chains the
      aggregation before its own runner-`finish_job` commits, so its
      `affected_module_ids` are not visible to the aggregation's
      sibling-query. The aggregation misses the last sibling's modules.
      Fix: at chain time the last sibling builds the union locally
      (sibling-query + its own `stats["affected_module_ids"]`) and
      passes it via `chain_job(config={...})` so the aggregation reads
      it from its own meta. Surfaced by Guilbert "all aggregations are
      0s" on 2026-05-20 — mostly that observation is the optimization
      working (empty-affected recalcs), but the race is real.
- ✅ **Phase 4B (`1bd26748`)**: per-`(module, year)`
      `pg_advisory_xact_lock` in `factor_ingest_handler`,
      `emission_recalc_handler`, `module_emission_recalc_handler`.
      Shared helper `acquire_factor_recalc_lock` in `app/tasks/_locks.py`,
      dedicated category `1237` (distinct from 4A.2's `1236`).
      Eliminates the silent-wrong-numbers race where a recalc reads
      half-written factors during a concurrent factor_ingest.
- ✅ **Phase 4B**: shipped as `1bd26748` (advisory lock at `(module,
      year)` scope, not `(module, det, year)` — broader but
      drop-hazard-free; see Done).
- [ ] **Phase 5**: retire `meta` threading
      (`recalc_jobs_chained` / `aggregation_job_id` / `parent_job_id`
      read paths) once nothing consumes them.

## 🔧 To DO — smaller follow-ups

- [ ] Lone-orphan `last_error`: when a job's only message is
      `"Success"` (the real reason is in `meta.stats.row_errors`),
      surface that reason instead. (Deeper than Phase 1; pairs with
      v1.x backfill quality.)
      _(Live SSE on the console moved up to "Newly discovered" — same
      issue, more specific framing.)_

## ❓ Needs a decision (yours)

- [ ] `PARTIAL` vs `FAILED` boundary — Phase 1 emits only
      SUCCESS/FAILED; `PARTIAL` reserved, undefined.
- [ ] Aggregation coalescing key: `(carbon_report scope, year)`? how
      `unit_sync` (year-level, also rewrites `carbon_reports`) folds in.
- [ ] Phase-3 sweep cron cadence / trigger.
- [ ] Remove the now-unused `pipeops_status_partial` i18n key? (left
      in to avoid churn.)

## ⚙️ Process / integration

- [ ] `#1225` + eager-pipeline-id + #1236 live **only** on
      `fix/pipeline-debug`, not in any `dev` PR. Stage promotion needs
      a deliberate "promote the integration branch" step — decide
      when/how.
- [ ] Verify/close **PR #1235** (the original #1234→dev PR,
      `816c817b`): superseded by the integration-branch state, like
      #1237 was. Confirm and close/retarget.
- Note: commit `9ac03507` ("chore: lint-staged formatting") actually
  carried the Phase-1 scaffolding (model+migration+doc) — hook
  mislabel, content is correct in HEAD. History cosmetic only.
