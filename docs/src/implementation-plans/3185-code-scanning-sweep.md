---
status: in-progress
issue: 3185
last_updated: 2026-11-05
summary: Clear the open CodeQL and Code Quality findings on dev. Two security alerts, dead code and test hygiene fixed in code; the remaining false positives listed for dismissal.
---

# Code-scanning sweep (#3185)

Source: exports of `code-scanning/alerts?state=open` (36) and
`code-quality/findings` (52) taken on 2026-11-05, computed at `6acac3325`. They
overlap heavily, so the same line often appears in both.

Delivered once a CodeQL run on `dev` shows the fixed alerts closed and the
table below is dismissed.

## Fixed in code

**Security**

- `py/stack-trace-exposure` (cs 736): the public `/health/deps` returned
  `str(e)` in its body. The error now goes to the log and `details` is gone from
  the response, as `/ready` already does. Status codes are unchanged, and nothing
  in this repo or the ops repo reads `details`.
- `js/http-to-file-access` (cs 674): `gen-api-types.mjs` no longer writes the
  fetched schema to a temp file. It checks the URL answers with JSON and passes
  the URL to `openapi-typescript`. The earlier `JSON.parse` round-trip did not
  clear this alert. If the backend dies between the check and the generation, the
  script now fails instead of falling back to the snapshot.

**Dead code and control flow**

- Unreachable re-check in `modules/purchase/handlers.py`; unused
  `IT_EMISSION_TYPES`.
- `get_role_provider` / `get_unit_provider`: `raise` moved after the `match`, so
  no fall-through is reported. Same behaviour.
- `tasks/bootstrap.py`: `functools.cache` replaces the `_BOOTSTRAPPED` global.
  A failed import is still retried on the next call.
- `tasks/runner.py` and `scripts/probe_pgbouncer_wait_timeout.py`: empty
  `except` blocks explain themselves. Comment only.

**Protocol stubs**

`py/ineffectual-statement` flags `...` bodies, and each code move opened new
alerts. The stubs in `schemas/factor.py`, `schemas/data_entry.py`,
`workflows/derived_entry_registry.py` and `modules/equipment/data_entries.py` now
have docstring bodies, which the type checker accepts.

**Tests**

- `lambda: _FakeSessionCM()` becomes `_FakeSessionCM`.
- `lambda: MagicMock()` in `dependency_overrides` becomes a hoisted mock, not a
  bare `MagicMock`: FastAPI reads an override's signature, so `MagicMock.__init__`
  parameters would become request parameters.
- `_ForbiddenSession.__getattr__` raises `AttributeError`.
- `import` + `from … import` duplicates replaced by string `monkeypatch` targets.
- Explicit `+` on the multi-line string in `test_db_pool_settings.py`; unused
  import removed from `results-csv.spec.ts`.

Regression test: `test_health_deps_response_omits_exception_details` in
`tests/unit/test_security_alert_fixes.py`.

## To dismiss

These stay open after the fixes. Rewriting the code to silence them would make
it worse. `cs` is a code-scanning alert, `cq` a Code Quality finding.

| Rule                          | Numbers                                                  | Location                                                                                                              | Why it is a false positive                                                                |
| ----------------------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `py/unused-import`            | cs 1313, 1314, 725, 726, 734; cq 347, 348, 258, 232, 239 | `test_factor_resolution_indexes.py`, `seed_emission_factors.py`, `seed_generic_factors.py`, `generate_mermaid_erd.py` | Side-effect import: it registers handlers or tables                                       |
| `py/unused-import`            | cq 487, 35                                               | `app/db.py`, `alembic/env.py`                                                                                         | Side-effect import: Alembic and the metadata need the models registered                   |
| `py/ineffectual-statement`    | cs 1355; cq 803, 864                                     | `test_sync_pipeline_stream_endpoint_pg.py:534`, `test_background.py:70`                                               | `await x` does have an effect                                                             |
| `py/non-iterable-in-for-loop` | cs 1348; cq 611                                          | `test_join_key_normalization_rules.py:57`                                                                             | `DataEntryTypeEnum` is an `Enum`, so it is iterable                                       |
| `py/unused-global-variable`   | cs 741; cq 557                                           | `models/module_type.py:74`                                                                                            | Used at `services/simulator_plan_service.py:535`                                          |
| `py/unused-local-variable`    | cq 244                                                   | `test_handler_registrations.py:135`                                                                                   | `data_session` is passed to the handler later in the test                                 |
| `py/cyclic-import`            | cs 728                                                   | `tasks/reference_ingest_tasks.py:14`                                                                                  | Deliberate lazy-import cycle (Plan 310-C); restructuring it is pipeline work, not cleanup |
