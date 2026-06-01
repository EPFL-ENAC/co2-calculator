# Bot Review TODOs: PR #1077

Source Branch: `feat/310-stale-stats-health`
PR Title: feat(310): stale-stats health endpoint [#1063]

---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Adds a passive observability backstop for the Plan 310-D aggregation pipeline by exposing a read-only health endpoint that reports stale/missing aggregation scopes (`module_type_id × year`) for monitoring systems (Datadog/Prometheus).

**Changes:**

- Added `GET /v1/sync/health/stale-stats?older_than_minutes=...` gated by `backoffice.data_management.view`, returning typed `why_stale` buckets.
- Implemented `DataIngestionRepository.find_stale_aggregations(threshold_minutes)` to seed from `carbon_report_modules × carbon_reports.year` and classify latest `job_type='aggregation'` per scope.
- Added Postgres-backed integration tests covering all `why_stale` buckets, permission gating, empty-modules behavior, and query parameter validation.

### Reviewed changes

Copilot reviewed 4 out of 4 changed files in this pull request and generated 2 comments.

| File                                                                              | Description                                                                                                               |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| docs/src/implementation-plans/310-d-architecture-followups.md                     | Adds/updates the umbrella plan doc for 310-D follow-ups, marking Follow-up 1 as delivered (with placeholders for others). |
| backend/tests/integration/services/data_ingestion/test_stale_stats_endpoint_pg.py | New integration test suite for `/v1/sync/health/stale-stats` across all buckets and edge cases.                           |
| backend/app/repositories/data_ingestion.py                                        | Adds repo helper to find and bucket stale aggregations; defines `WhyStaleLiteral` and `StaleStatsRow` TypedDict.          |
| backend/app/api/v1/data_sync.py                                                   | Adds the new health endpoint + response model wired to the repository helper and permission gate.                         |

---

### File: `backend/app/api/v1/data_sync.py` (Line 194) — Copilot

`StaleStatsEntry` docstring references `GET /sync/health/stale-stats`, but the route is mounted under the `/v1/sync` router (tests call `/v1/sync/health/stale-stats`). Please update the docstring so it matches the actual public path to avoid misleading API consumers / operators.

---

### File: `docs/src/implementation-plans/310-d-architecture-followups.md` (Line 26) — Copilot

This plan doc still contains a `PR #<TBD>` placeholder in Follow-up 1's status section. Since this PR is delivering Follow-up 1, please replace the placeholder with the actual PR number/link so the plan stays traceable after merge.

---
