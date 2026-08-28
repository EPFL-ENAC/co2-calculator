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
- **Origin:** `versions/2026_08_20_1628-ad1593afc72f_initial_migration.py` (previously
  `versions copy/2026_05_04_0952-..._search_locations.py`, before the 2211 collapse)

## Captured in models — verify, don't hand-write

These were once raw SQL but are now in `__table_args__` / `Column(...)`, so autogenerate
emits them. Listed here only so a future collapse can confirm they survived.

- Partial / expression unique indexes:
  `uq_factor_identity`, `uq_factor_identity_no_year`, `uq_emission_recalc_active`,
  `uq_aggregation_active`, `ix_data_ingestion_jobs_is_current_unique`,
  `ix_data_ingestion_jobs_pending`, `audit_document_one_current_idx`,
  `uq_member_role_per_module` (`data_entry.py`), `uq_active_datasource_per_module`
  (`connector.py`), `uq_carbon_projects_unit_plan_name` (`carbon_project.py`). It was
  found live only in migration history during the 2211 collapse — moved into
  `__table_args__` in the same PR instead of hand-writing it into the new migration.
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
- **`uq_carbon_projects_unit_type_nonplan`** partial unique index on `carbon_projects`
  (`unit_id`, `carbon_report_type` where `carbon_report_type <> 'Simulator_Plan'`).
  Dropped by migration `ff4f9bac0339` (scope simulator explore projects per user) in
  favour of two narrower partial indexes now in `__table_args__`:
  `uq_carbon_projects_unit_explore_creator` and `uq_carbon_projects_unit_type_calculator`.

## Data migrations / backfills — not part of schema

Ignored on collapse (pre-v1.x drops the DB between deploys, so no backfill is needed):
`backfill_carbon_project_id`, `DELETE FROM year_configuration WHERE provider <> 'DEFAULT'`,
`migrate_data_ingestion` (2026-06-15 collapse); `strip_legacy_primary_factor_id_and_null_`,
`strip_legacy_status_from_entry_json`, `backfill_data_entries_year_and_unit_id_`,
`migrate_mice_research_facility_type_to_`, `migrate_legacy_traveler_sentinels_to_1_`,
`rename_process_emissions_quantity_to_quantity_kg` (#2025) (2211 collapse — the last one's
round-trip test, `test_quantity_kg_migration_pg.py`, was deleted with it).
