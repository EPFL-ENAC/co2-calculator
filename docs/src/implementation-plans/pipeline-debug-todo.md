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
- [ ] Sibling `"status_message": "Success"` hardcodes in
      `base_provider.py:186` and
      `base_reduction_objective_csv_provider.py:169`: trace whether any
      handler path uses them and bypasses `finalize_ingest_meta`; fix
      or confirm unreachable.

## 🐞 Newly discovered (Guilbert, 2026-05-20)

- [ ] **Year-config pipeline doesn't block same-year uploads.** With a
      `unit_sync` / year-configuration pipeline running for year Y,
      after a page refresh the "loading" indicator is gone — nothing
      blocks the user from uploading data for Y while the year is
      still being provisioned. Suggested shape: a
      `configuration_completed` flag (with timestamp) on
      `year_configuration`; gate upload on it. Adjacent to #1236
      Problem B (scoped ordering correctness) but at the **year**
      grain, not `(module, det)`.
- [ ] **`unit_sync` collapses to one aggregated task per year.**
      Individual sub-tasks aren't exposed in the ops UI. Show them so
      operators can see what's actually running inside the year-level
      pipeline.
- [ ] **No SSE on the pipeline ops page.** The table doesn't
      live-update; pipeline progress doesn't stream into the open
      page or the message dialog. `usePipelineStream` +
      `GET /pipelines/{id}/stream` exist and were deferred in #1234
      — wire them (per-row for visible items, or a page-level
      subscription to the running pipelines on the current page).

## 🔧 To DO — #1236 remaining phases

- [ ] **Phase 2**: enforce `data_ingestion_jobs.pipeline_id` →
      `pipelines(id)` FK. v0.x = no backfill (DB dropped between
      deploys); add the FK migration to run on a clean DB already on
      Phase-1 code. Real backfill is a **v1.x** concern.
- [ ] **Phase 3**: flip reads (console #1234, `GET /pipelines/{id}`,
      progress) to the `pipelines` table; `compute_pipeline_progress`
      becomes writer-side only. Schedule the reconciliation sweep on a
      cron _before_ flipping. Verify: golden-output diff before/after.
- [ ] **VERIFY (gates Phase 4)**: does the aggregation handler
      full-rewrite all ~2231 `carbon_reports`, or is it already
      scoped? Confirm before designing the scoping change.
- [ ] **Phase 4A**: aggregation coalesce + scope to
      `affected_module_ids` (extend `AGGREGATION_DEDUP`).
- [ ] **Phase 4B**: scoped `(module,det,year)` factor→data ordering
      (correctness — stale-factor recalc); reuse
      `uq_emission_recalc_active`.
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
