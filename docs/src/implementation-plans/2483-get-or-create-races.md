---
status: in-progress
issue: 2483
last_updated: 2026-08-28
summary: Guard explorer/calculator get-or-create with a SAVEPOINT so the race loser returns the winner instead of a 500
---

# 2483 — Explorer/Calculator get-or-create races 500

## Problem

Found during the #2445 audit. Three unguarded read-then-insert paths in
`CarbonReportService` race against their (semantic, kept) unique indexes:

- `_get_explore_project() or _create_explore_project()` vs
  `uq_carbon_projects_unit_explore_creator`
- `_get_project(CALCULATOR) or _create_project()` vs
  `uq_carbon_projects_unit_type_calculator`
- `create_explore`'s report INSERT vs `uq_carbon_reports_project_year`

No `IntegrityError` handling exists on the path and there is no global
handler, so the loser surfaces as a **500** — and the frontend produces the
race routinely (`workspace.ts` does GET → on 404 → POST, so two tabs or a
double-click both see 404 and both POST).

## Fix

Wrap each insert in a SAVEPOINT (`session.begin_nested()`); on
`IntegrityError`, re-fetch and return the committed winner. The savepoint
confines the rollback to the failed insert, so the request's other staged
writes survive and the route's commit stays where it belongs. The loser gets
a correct response with the winner's row. When the re-fetch finds nothing
(the error wasn't the race), the original error re-raises — no silent
fallback.

`create_explore`'s recovered path returns the winner's report **without**
re-creating modules: the loser only unblocks after the winner's transaction
(report + modules) committed.

## Test

`backend/tests/unit/services/test_carbon_report_service.py`: the SQLite test
schema intentionally omits the partial unique indexes, so the loser's
`UniqueViolation` is injected at the flush (projects) or the repo insert
(report). Three regression tests assert the winner's row comes back for
explore project, calculator project, and explore report.

## Deliverables

- [x] SAVEPOINT guards in `_create_project`, `_create_explore_project`,
      `create_explore`
- [x] Regression tests (three race paths)
- [ ] Flip to `delivered` on merge
