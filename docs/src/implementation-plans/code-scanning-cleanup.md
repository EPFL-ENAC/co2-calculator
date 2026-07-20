---
status: delivered
issue: none (GitHub code-scanning sweep)
last_updated: 2026-07-16
summary: Resolve all 84 open CodeQL code-scanning alerts — 2 security fixes with regression tests, ~30 mechanical cleanups, and triage dismissals for false positives / deliberate patterns.
---

# Code-scanning cleanup

Branch `chore/code-scanning`. Source: the open alerts on
https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning.

## Security fixes (errors)

- **py/log-injection** (`app/repositories/location_repo.py`): the raw user
  search `query` was interpolated into log lines. Newlines are now stripped
  (`safe_query`) before logging so a crafted query can't forge log entries.
- **py/stack-trace-exposure** (`app/main.py` `/ready`): the readiness
  response returned `details` containing `str(e)` for DB / Accred failures
  to unauthenticated callers. Details now stay in the warning log only.
- Regression tests: `tests/unit/test_security_alert_fixes.py`.

## Behavior fix

- `get_unit_provider` `case _` silently fell back to the database provider
  on an unknown provider type. Now raises `ValueError`, mirroring
  `get_role_provider` (no-silent-fallbacks invariant).

## Mechanical fixes

- Duplicate constant block deleted in `core/constants.py`; duplicate
  `data_entry_type_id` computation deleted in `api/v1/carbon_report_module.py`.
- Unreachable re-check deleted in `modules/purchase/schemas.py`.
- Implicit string concatenation in seed SQL lists made explicit with `+`.
- `exit()` → `sys.exit()` in `scripts/{audit,migrate}_test_users.py`;
  inline `traceback` import hoisted.
- Unused `logger` removed from `tasks/reference_ingest_tasks.py`.
- Commented-out code removed (`carbon_report_module_repo.py`); the parked
  metier-denied test in `test_permission_scope_e2e.py` is now a real test
  under `@pytest.mark.skip` instead of a comment block.
- Test hygiene: empty `except` blocks got explanatory comments, unused
  locals/imports removed, `import` + `from-import` duplication resolved,
  `lambda: _user()` → `_user`.
- `frontend/scripts/gen-api-types.mjs`: live OpenAPI payload is round-tripped
  through `JSON.parse` before staging, so non-JSON responses fall back to
  the snapshot.

## Dismissed as false positive / won't fix (not code changes)

- `py/ineffectual-statement` on `...` bodies: `typing.Protocol` stubs.
- `py/unused-import` on side-effect imports (model registration in
  `db.py`/`alembic/env.py`, handler registration in seed modules).
- `py/mixed-returns` on `match` statements whose `case _` raises.
- `py/cyclic-import` across `app/tasks/*` and the two carbon-report
  services: deliberate, documented lazy-import cycles (Plan 310-C);
  restructuring the pipeline is out of scope while the lead is away.
- `py/unexpected-raise-in-special-method`: the `_ForbiddenSession`
  sentinel raises `AssertionError` by design.
- `py/unused-global-variable` on `_BOOTSTRAPPED`: it is read as the
  idempotency guard.
