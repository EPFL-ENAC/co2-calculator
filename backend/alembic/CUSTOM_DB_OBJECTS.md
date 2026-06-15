# Custom DB objects (not derivable from models)

`alembic revision --autogenerate` reads SQLModel/SQLAlchemy metadata. Anything that
isn't expressible in the models is **invisible** to autogenerate and will be silently
dropped if you collapse migrations. This file is the source of truth for those objects.

**When collapsing migrations, re-apply every item below by hand and update this file.**

## Active — MUST be present in the collapsed migration

### `pg_trgm` extension

- **What:** `CREATE EXTENSION IF NOT EXISTS pg_trgm`
- **Why:** `locations.keywords` has a trigram GIN index
  (`ix_locations_keywords ... USING gin (keywords gin_trgm_ops)`). The index is in the
  model (`postgresql_using='gin'`, `postgresql_ops={'keywords': 'gin_trgm_ops'}`) and
  autogenerate emits the `CREATE INDEX`, but **not** the extension it depends on.
- **Where:** added at the top of `upgrade()` in the collapsed migration; dropped at the
  end of `downgrade()`.
- **Origin:** `versions copy/2026_05_04_0952-..._search_locations.py`

## Captured in models — verify, don't hand-write

These were once raw SQL but are now in `__table_args__` / `Column(...)`, so autogenerate
emits them. Listed here only so a future collapse can confirm they survived.

- Partial / expression unique indexes:
  `uq_factor_identity`, `uq_factor_identity_no_year`, `uq_emission_recalc_active`,
  `uq_aggregation_active`, `ix_data_ingestion_jobs_is_current_unique`,
  `ix_data_ingestion_jobs_pending`, `audit_document_one_current_idx`.
- Enum values added over time via `ALTER TYPE ... ADD VALUE`
  (`sync_status_enum`: `SKIPPED`, `RETRY_QUEUED`; `ingestion_method_enum`: `computed`;
  `target_type_enum`: `REFERENCE_DATA`, reduction-objective values). These come from the
  Python enums, so they appear in the `sa.Enum(...)` of the collapsed migration.

## Retired — intentionally NOT recreated

Do not re-add these; the final schema no longer uses them.

- **Custom collations** `ch_it_ci_ai`, `ch_de_ci_ai`, `ch_fr_ci_ai` and their
  collation-based indexes (`idx_locations_{name,keywords,municipality}_{it,de,fr}`).
  Created in `add_collation`, then dropped by `search_locations` in favour of trigram
  search. Nothing in the final schema references them.
- **`update_updated_at_column()` function + `update_data_entries_updated_at` trigger.**
  Auto-set `data_entries.updated_at` on UPDATE. Dropped on collapse: the model now uses
  `onupdate=datetime.utcnow` and raw-SQL writers set `updated_at` explicitly.
  ⚠️ If a future raw `UPDATE data_entries ...` omits `updated_at`, that column will go
  stale — re-introduce the trigger if that ever happens.

## Data migrations / backfills — not part of schema

Ignored on collapse (pre-v1.x drops the DB between deploys, so no backfill is needed):
`backfill_carbon_project_id`, `DELETE FROM year_configuration WHERE provider <> 'DEFAULT'`,
`migrate_data_ingestion`.
