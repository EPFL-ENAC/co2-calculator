---
status: in-progress
issue: 2904
last_updated: 2026-09-22
summary: Collapse the 20 Alembic migrations into one before go-live; dev, stage and prod are dropped and rebuilt from it. Label seeds stay as reference data in the new migration.
---

# Consolidate Alembic migrations before go-live

**Goal:** one migration file that builds the current schema, with no backfills or
one-off cleanups in history. Dev, stage and prod are dropped and rebuilt from it on
go-live day (2026-09-22). Same mechanism as [#2211](2211-consolidate-alembic-files.md).

`backend/alembic/CUSTOM_DB_OBJECTS.md` is the checklist; this collapse rewrote it
(it still listed indexes dropped since #2211 and missed everything added after).

## Audit of the 19 migrations since #2211

- **Schema, already in models** (autogenerate re-emits): pod columns, the
  `carbon_projects`/`carbon_reports` indexes, `ix_factors_res_*`, the recalc dedup
  pair, check constraints, `roles_empty_since`, `runs_jobs`, the `data_entry_emissions`
  columns and covering index.
- **Backfills / cleanups** (dropped): `277bf6757926` guard, `95fe938000d4`,
  the `1a9837dd65a3` backfill `UPDATE`.
- **Migration-only index:** `ix_classification_translations_label_trgm`
  (`956c36805397`). Moved into `ClassificationTranslation.__table_args__`, pinned by
  `tests/unit/models/test_classification_translation_trgm_index.py`.
- **Migration-only check (found while verifying):**
  `ck_data_ingestion_jobs_unit_specific_has_entity_id` sat in a first
  `__table_args__` that a second one in `DataIngestionJob` overrode, so it never
  reached the metadata. Merged into the single tuple, Postgres-only (the SQLite
  unit schema never enforced it), pinned by
  `tests/unit/models/test_data_ingestion_job_check_constraint.py`. An AST scan
  found no other class with a duplicate `__table_args__`.
- **Reference data:** the three label seeds (`3b5609f893f4`, `fd12a7a0946f`,
  `7bff78de3264`) are the only source of `classification_translations` rows.
  Maintainer decision: keep them as an `op.bulk_insert` in the new migration, so every
  fresh DB gets them from the helm migration Job with no manual step.

## Steps

1. Model: declare the trigram index (+ unit test).
2. `git rm` the 20 files; delete `test_2458_orphaned_explore_cleanup` (it tested a
   dropped data migration); repoint comments naming the seed revisions.
3. Generate against an empty local DB: `DB_URL=<local scratch> make db-revision`.
4. Hand edits only: `CREATE EXTENSION pg_trgm` at the top, the label `bulk_insert`.
5. Prove it: a `pg_dump --schema-only` of the old chain and of the new migration
   match (modulo the three check constraints, `NOT VALID` in the old chain), and a
   second autogenerate proposes only the known `uq_emission_recalc_active_scoped`
   noise. `make test-db-migrate` passes.

## Result

New head: `128d2947054c` (`2026_09_22_1021-128d2947054c_initial_migration.py`).
Schema-only dump of the old chain vs the new migration on local scratch DBs:
identical except the three checks (`NOT VALID` in the old chain) and the position
of late-added columns in `data_entry_emissions` and `pods`. A second autogenerate
proposed only the `uq_emission_recalc_active_scoped` re-render. 58 label rows
land.

## Rollout

Every environment was at `9da4a65ef1e3`, which no longer exists. Each DB is dropped
and rebuilt with `alembic upgrade head` from this branch **before** its migration Job
runs a new image; otherwise the Job fails with "Can't locate revision". Until the
release ships, an Argo re-sync of the old image fails the same way (sync blocked, pods
keep serving). Once prod is built from the new revision, its ID is frozen: any fix is
a new migration on top.
