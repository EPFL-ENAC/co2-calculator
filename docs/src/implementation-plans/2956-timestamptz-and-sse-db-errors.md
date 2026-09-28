---
status: in-progress
issue: 2956
last_updated: 2026-09-28
title: "timestamptz for four naive columns; SSE streams end cleanly on DB errors"
summary: "Follow-ups from #2946/#2954. A DB error in an SSE stream's poll loop surfaced as Starlette's 'response already started' RuntimeError, with the real error only in __cause__. Both SSE streams now log it and end: the job stream with its existing 'Job not found' event shape, the pipeline stream silently. The last four naive datetime columns become timestamptz with aware writers; migration e88e9dc9e75e pins the session to UTC, so no row shifts and (PG 12+) no table is rewritten."
---

# timestamptz for four naive columns; SSE streams end cleanly on DB errors

## SSE streams: mid-stream DB errors

### Problem

`job_stream_by_id` and `pipeline_stream_by_id` in `api/v1/data_sync.py` open
a `SessionLocal()` on every poll, after the 200 has been sent. `main.py`
registers `db_unavailable_handler` for `DBAPIError` and SQLAlchemy's pool
`TimeoutError`. Once a response has started, Starlette
(`_exception_handler.py`) re-raises any exception with a registered handler as
`RuntimeError("Caught handled exception, but response already started.")`.
The DB error survived only as `__cause__`, so log queries keyed on
`OperationalError` missed it (plan
[2049](2049-async-db-health-poller.md), last section).

### Decisions

1. **One wrapper, two callers.** `_end_stream_on_db_error` re-yields the
   stream's events and catches `DBAPIError` and the pool `TimeoutError`
   only. It logs the real exception with `exc_info` and the request path,
   then ends the stream. The poll is the only DB access inside either
   generator, so wrapping the generator is the same as catching in the poll
   loop. Any other exception still propagates.
2. **Every `DBAPIError`, not only "unavailable".** The stream has no 503 to
   pick, so it doesn't need `db_unavailable_handler`'s predicate. The
   terminal message therefore says "database error", not "temporarily
   unavailable".
3. **Job stream: the "Job not found" shape.** It emits
   `{"job_id", "status_message": "Job status unavailable: database error"}`
   and returns. `subscribeToJobUpdates` (`stores/backofficeDataManagement.ts`)
   treats neither payload as finished. The server close fires `onerror`,
   which unsubscribes and calls the caller's `onError` ("connection lost").
   A `state: FINISHED, result: ERROR` payload was rejected: it would write a
   fake failed row into `syncJobs` and fire `onFail` for a job that may
   still be running.
4. **Pipeline stream: no event.** Its only terminal shape is a
   `pipeline-update` with `stream_closed: true`, which needs real `jobs` and
   `progress`. Without them it would clobber the store entry.
   `usePipelineStream` relies on native `EventSource` retry. The reconnect
   runs the pre-stream check, where a DB that is still down answers 503 when
   `db_unavailable_handler` judges it unavailable, 500 otherwise. Either
   non-200 closes the `EventSource` for good. Client behaviour matches the
   aborted connection of before; only the log changes.
5. **No frontend change.**

### Found, not fixed

- `ModuleTable.vue` passes no `onError` to `subscribeToJobUpdates`, and
  `useSubmoduleConfig.ts`'s `onError` only resets the spinner. Both were
  already silent when the stream ended on "Job not found".
- No other stream reads the DB after the response starts. The audit
  exports (`api/v1/audit.py`) and the backoffice exports
  (`api/v1/backoffice.py`) build the whole body before responding.
  `report_detailed`'s lazy generator only reads a temporary zip file.
- **The pipeline badge freezes silently** when a DB outage outlasts the
  browser's retry delay. `usePipelineStream.ts` has no `onerror`, and
  `activeStreams.delete` only runs in `closeStream`, so the closed source
  stays registered and a re-subscribe does not reopen it. Same as before
  this PR.

### Tests

`tests/unit/v1/test_data_sync_stream_db_errors.py` drives both generators
with a repository that fails on the second poll:

- job stream, for `OperationalError` and the pool `TimeoutError`: the
  first event is the real state, the second and last is the terminal
  payload, and the log record's `exc_info` holds the raised error;
- pipeline stream: one `pipeline-update`, then the stream ends and the error
  is logged;
- a `ValueError` still propagates.

The first two fail without the fix: the DB error escapes the generator.

## timestamptz for four naive columns

### Problem

#2954 pinned four columns to plain `timestamp` to unbreak dev:
`year_configuration.updated_at`, `audit_documents.changed_at`,
`audit_documents.synced_at` and `users.last_login`. The other 20 datetime
columns are `DateTime(timezone=True)`. Their writers used the deprecated
`datetime.utcnow()`, while `audit_service` and `user_repo` already wrote
aware `datetime.now(UTC)` values into the naive columns.

### Decisions

1. **Models declare `sa_type=DateTime(timezone=True)`**, like the other 20
   columns. `test_datetime_column_types.py` stays green: it only forbids
   SQLModel's automatic `UTCDateTime`.
2. **Writers produce aware values.** A new `default_aware_utcnow` in
   `models/_field_defaults.py` feeds `AuditDocument.changed_at` and
   `YearConfiguration.updated_at` (default and `onupdate`).
   `default_utcnow` stays naive: `data_entries.created_at/updated_at` are
   still `timestamp` columns.
   `connector.py`'s identical private `_utcnow` is deleted and imports it.
3. `year_configuration.create_audit_entry` no longer passes
   `changed_at=datetime.utcnow()`, so the model default applies. The four
   `synced_at` writers in `audit_sync_service` use `datetime.now(UTC)`. The
   `seed_year_configuration` script binds `updated_at` as `timestamptz`.
4. **Reads.** No Python code compares or subtracts these fields against a
   naive datetime. The audit filters compare in SQL, and a naive parameter
   is cast in the session TimeZone there.

### Migration (`e88e9dc9e75e`)

Generated with `make db-revision` against a fresh local DB at
`128d2947054c`, then two minimal edits:

1. **Four `alter_column` ops only.** `TIMESTAMP()` → `DateTime(timezone=True)`,
   each with its downgrade. The autogenerated `uq_emission_recalc_active_scoped`
   drop/create pair was pruned: it is the documented false positive in
   `backend/alembic/CUSTOM_DB_OBJECTS.md`, where Postgres re-renders the
   expression.
2. **`op.execute("SET LOCAL TIME ZONE 'UTC'")` opens `upgrade()` and
   `downgrade()`.** The timestamp → timestamptz cast reads stored values in
   the session TimeZone, and the reverse cast renders in it. Pinning UTC
   means no row shifts either way. `SET LOCAL` lasts until the end of the
   transaction, and `alembic/env.py` runs a single `begin_transaction()`, so
   it holds for the whole migration.
3. **`SET LOCAL lock_timeout = '5s'` follows it.** Every authenticated
   request reads `users`. If an open transaction holds it, the ALTER fails
   after 5 s and can be re-run, instead of queueing every request behind it.

**No table rewrite.** The
[PostgreSQL 12 release notes](https://www.postgresql.org/docs/release/12.0/)
(E.23.3.1.4, General Performance): "Allow `ALTER TABLE ... SET DATA TYPE`
changing between `timestamp` and `timestamptz` to avoid a table rewrite when
the session time zone is UTC". Indexes on an affected column are still
rebuilt ([commit](https://git.postgresql.org/pg/commitdiff/3c5926301)); none of
the four columns is indexed.

**Verified locally (PG 18).**

- `relfilenode` of `audit_documents`, `users` and `year_configuration` is
  unchanged across upgrade **and** downgrade, so no rewrite in either
  direction.
- The four columns come out `timestamp with time zone`.
- `alembic check` reports only the known index false positive.

**Checked on a deployed DB, as the app role (2026-09-25).**

- `timezone` = `Etc/UTC`, PostgreSQL 18.4. The maintainer confirms every
  environment has always run `Etc/UTC`.
- `audit_documents` = 8896 kB, about 2214 rows.

`Etc/UTC` means the aware values `audit_service` wrote into the naive
`changed_at` were stored as UTC wall time: no mixed zones, and the cast is
exact.

### Visible changes

- **Audit log times move +1 h (winter) or +2 h (summer) in the UI. That is
  the correction.** `AuditTable.vue` and `AuditDetailDrawer.vue` render
  `new Date(changed_at)`. JS reads an offset-less date-time as local time,
  so the UI showed UTC wall-clock time as if it were Zurich time. The API
  now sends an offset, so the times are right. `synced_at`, `last_login`
  and year-configuration `updated_at` are typed in the frontend but not
  displayed. No frontend change.
- The audit CSV/JSON exports gain the UTC offset on `changed_at`.
- **Elasticsearch `@timestamp` jumps by the Zurich offset between old and
  new documents.** `elasticsearch/client.py:format_timestamp` labels a
  naive datetime as Europe/Zurich, so documents indexed until now carry a
  `@timestamp` 1–2 h early. Aware values are converted correctly, so new
  syncs are right. Old documents are not re-indexed; tracked in #2963.

### Found, not fixed

- `data_entry_emissions.computed_at` is already `timestamptz` but defaults
  to the naive `default_utcnow`. That is correct only while the session is
  UTC. Tracked in #2965.
- CI's `test_alembic_migrations.py` never compares the models with the
  migrated schema, so it would not have caught a missing migration here.
  Tracked in #2964.
- Three PG integration tests (`test_backoffice_factor_upload_green_box_pg.py`,
  `test_plan_310b_factor_reupload_endpoint_pg.py`,
  `test_headcount_post_statement_budget_pg.py`) explain their psycopg driver
  choice with the naive `changed_at`. Once the migration lands, that reason
  is gone for the first two.

### Tests

In `tests/unit/models/test_aware_datetime_writers.py`, `test_audit_sync_service.py`
and `test_user_repo.py`, the writers produce aware in-memory values. A DB
round trip would prove nothing: SQLite drops tzinfo, and timestamptz always
comes back aware.

- `AuditDocument.changed_at`'s default;
- `YearConfiguration.updated_at`'s default and `onupdate`;
- `create_audit_entry`;
- `synced_at` on the single-record, success, conflict and skipped paths;
- `last_login` on create and update.

All but `last_login` fail without the change. That writer was already
aware; its assertions guard it now.
