---
status: in-progress
issue: 310
last_updated: 2026-05-06
title: "310 — Backoffice recalculation upon factor updates"
summary: "Recalculate downstream emission data when operators update factors via the backoffice."
---

# 310 — Backoffice recalculation upon factor updates

## Context

When operators update emission factors via the backoffice (CSV upload or factor sync), all
derived data downstream of those factors becomes stale: `data_entry_emissions` rows still
reference the old factor values, and `carbon_reports.stats` aggregates still reflect the
pre-update totals. Today this requires a manual recalculation step that operators forget,
leading to inconsistent reporting until the next batch run.

The naive fix — "compute emissions inline during factor ingest" — surfaced concurrency bugs:
multiple bulk pipelines for different modules race on the same `data_entry_emissions` and
`carbon_reports` tables, two pods can claim the same job under the existing
`is_current` flag, and the orchestration layer (`BackgroundTasks` + ad-hoc dispatch) had no
recovery for crashed workers.

## Decisions

After scoping the work, the issue was decomposed into **four phased plans**, each landing
independently. Read [`310-overview.md`](./310-overview.md) for the architectural rationale.

| Plan | Focus                                                                                                      | File                                                                                 |
| ---- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| A    | Pod safety + atomic claim + safety poller + manual recovery endpoint                                       | [`310-a-pod-safety.md`](./310-a-pod-safety.md)                                       |
| B    | Factor upsert-in-place (JSONB classification, `last_seen_job_id`), auto-recalc trigger, unit-sync tracking | [`310-b-factor-pipeline.md`](./310-b-factor-pipeline.md)                             |
| C    | Handler registry + unified `run_job` runner + observability columns                                        | [`310-c-dag-handler-registry.md`](./310-c-dag-handler-registry.md)                   |
| D    | Bulk path: pure-async ingest → recalc → aggregation chain (Path 2 only)                                    | [`310-d-pipeline-responsibility-split.md`](./310-d-pipeline-responsibility-split.md) |

Cross-cutting principles that hold across all four plans:

- **One writer per table on the bulk path.** `data_entries` written only by `csv_ingest` /
  `api_ingest`; `data_entry_emissions` only by `emission_recalc`; `carbon_reports.stats`
  only by `aggregation`.
- **Path 1 (interactive UI) is unchanged.** Single-row module edits stay synchronous; their
  inline writes are scoped to one row and trivially serialized by the request.
- **Postgres is the queue.** Atomic claim via partial unique index + `SELECT FOR UPDATE
SKIP LOCKED` polling. No external broker (Celery / Redis / RabbitMQ).
- **Recalculation is idempotent.** Handlers can be replayed without producing duplicate
  derived rows; aggregation always uses `ON CONFLICT DO UPDATE`.

## Out of scope

- Path 1 inline emission compute (deliberate UX choice for the interactive editor).
- Migration to a third-party job queue. Decision rationale lives in
  [`310-overview.md`](./310-overview.md#why-not-celery).
- Backfill of factor history beyond what `last_seen_job_id` exposes (Plan B).

## Status

Plan A has shipped on `feat/310-backoffice-recalculation-upon-factors-update`. Plans B, C,
D are sequenced behind it. See each plan's "Tests" section for acceptance criteria.
