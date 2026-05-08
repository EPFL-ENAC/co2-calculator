# Bot Review TODOs: PR #1022

## Source Branch: `chore/310c-pg-fixture-310b-indexes`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR refactors the Postgres integration-test setup for Plan 310B by moving repeated partial-index DDL into a shared fixture. It keeps the test suite aligned with the production factor-upsert schema while reducing duplication across the data ingestion tests.

**Changes:**

- Add a shared `pg_dsn_with_310b` fixture in `conftest.py` that installs Plan 310B’s partial unique indexes once per test.
- Update factor pipeline and stale-endpoint integration tests to consume the shared fixture instead of creating indexes inline.
- Update the factor reupload endpoint test to use the shared fixture while preserving its psycopg driver workaround.

### Reviewed changes

Copilot reviewed 4 out of 4 changed files in this pull request and generated no comments.

| File                                                                                              | Description                                                                                                                  |
| ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `backend/tests/integration/services/data_ingestion/conftest.py`                                   | Adds the shared helper and fixture that install Plan 310B partial unique indexes on top of the fresh test schema.            |
| `backend/tests/integration/services/data_ingestion/test_plan_310b_factor_pipeline_pg.py`          | Replaces repeated inline index creation with the shared fixture across repository-level factor pipeline tests.               |
| `backend/tests/integration/services/data_ingestion/test_factors_stale_endpoint_pg.py`             | Switches the stale endpoint integration test app fixture to the shared indexed DSN fixture.                                  |
| `backend/tests/integration/services/data_ingestion/test_plan_310b_factor_reupload_endpoint_pg.py` | Switches the end-to-end factor reupload test app fixture to the shared indexed DSN fixture and removes duplicated setup DDL. |

---

## Action Items

_No substantive items — Copilot reviewed all 4 changed files and generated no inline comments._
