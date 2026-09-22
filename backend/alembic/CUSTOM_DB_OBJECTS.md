# Custom DB objects (not derivable from models)

`alembic revision --autogenerate` reads SQLModel/SQLAlchemy metadata. Anything that
isn't expressible in the models is **invisible** to autogenerate and will be silently
dropped if you collapse migrations. This file is the source of truth for those objects.

**When collapsing migrations, re-apply every item below by hand and update this file.**
Last collapse: #2904 (2026-09-22), into `versions/2026_09_22_1021-128d2947054c_initial_migration.py`.

## Active — MUST be present in the collapsed migration

### `pg_trgm` extension

- **What:** `CREATE EXTENSION IF NOT EXISTS pg_trgm`
- **Why:** two trigram GIN indexes depend on it — `ix_locations_keywords`
  (`location.py`) and `ix_classification_translations_label_trgm`
  (`classification_translation.py`). Autogenerate emits both `CREATE INDEX`
  statements, but **not** the extension they need.
- **Where:** top of `upgrade()`; dropped at the end of `downgrade()`.

### `classification_translations` label rows

- **What:** 58 rows (en + fr) labeling code-valued classification fields:
  `sius_code`, `energy_type`, `name` (fuels), `room_type`, `researchfacility_type`,
  `service_type`.
- **Why:** reference data, not a backfill. The stored values are codes in any
  locale, nothing else seeds these rows, and without them the UI shows raw codes
  (`51`, `natural_gas`). A factor-CSV upload later upserts over the fr rows.
- **Where:** `op.bulk_insert` right after `create_table("classification_translations")`.
- **Origin:** seed migrations `3b5609f893f4`, `fd12a7a0946f`, `7bff78de3264`,
  folded in by #2904.

## Captured in models — verify, don't hand-write

These were once raw SQL or migration-only, but now live in `__table_args__` /
`Column(...)`, so autogenerate emits them. On a collapse, grep the new migration for
each name. A missing one means the model didn't round-trip — fix the model, don't
hand-write the index.

- Partial / expression unique indexes: `uq_factor_identity`,
  `uq_factor_identity_no_year` (`factor.py`); `uq_emission_recalc_active_unscoped`,
  `uq_emission_recalc_active_scoped`, `uq_aggregation_active`,
  `ix_data_ingestion_jobs_is_current_unique`, `ix_data_ingestion_jobs_pending`
  (`data_ingestion.py`); `audit_document_one_current_idx` (`audit.py`);
  `uq_member_role_per_module` (`data_entry.py`); `uq_active_datasource_per_module`
  (`connector.py`); `uq_carbon_projects_unit_type_calculator` (`carbon_project.py`);
  `uq_carbon_reports_project_grant` (`carbon_report.py`).
- Factor-resolution expression indexes: 8 × `ix_factors_res_<key>` (`factor.py`,
  one per `FACTOR_RESOLUTION_INDEX_KEYS`, pinned by
  `tests/unit/models/test_factor_resolution_indexes.py`).
- Trigram GIN indexes: `ix_locations_keywords` (`location.py`),
  `ix_classification_translations_label_trgm` (`classification_translation.py`).
  The second was migration-only until #2904, when it moved into the model; every
  autogenerate before that proposed dropping it.
- Covering index with `INCLUDE` columns: `ix_dee_module_type_entry`
  (`data_entry_emission.py`, #2527) — `(carbon_report_module_id, data_entry_type_id,
data_entry_id) INCLUDE (kg_co2eq, emission_type_id, primary_factor_id, scope)`.
  The seeder re-creates it by hand in `seed_post_all.py` after dropping it in
  `seed_clean_data.py`; that DDL must stay byte-equivalent to the model's or the
  next autogenerate churns on it.
- Check constraints: `ck_data_entries_data_not_null`,
  `ck_data_entries_data_is_non_empty_object` (`data_entry.py`),
  `ck_data_ingestion_jobs_unit_specific_has_entity_id` (`data_ingestion.py`). Their
  original migrations added them `NOT VALID` to skip a table scan on live data; the
  collapsed migration creates them as plain checks on empty tables.
  `ck_data_ingestion_jobs_unit_specific_has_entity_id` was migration-only until
  #2904: `DataIngestionJob` declared `__table_args__` twice and the second
  silently replaced the first.
- Enum values added over time via `ALTER TYPE ... ADD VALUE`. These come from the
  Python enums, so they appear in the `sa.Enum(...)` of the collapsed migration.

### Known autogenerate noise

`uq_emission_recalc_active_scoped` keys on a `::jsonb` cast expression, which
autogenerate re-renders on every run and proposes to drop and recreate. It is a false
positive: prune it from any new revision.

## Retired — intentionally NOT recreated

Do not re-add these; the final schema no longer uses them.

- **Custom collations** `ch_it_ci_ai`, `ch_de_ci_ai`, `ch_fr_ci_ai` and their
  collation-based indexes (`idx_locations_{name,keywords,municipality}_{it,de,fr}`),
  replaced by trigram search.
- **`update_updated_at_column()` function + `update_data_entries_updated_at` trigger.**
  The model now uses `onupdate=datetime.utcnow` and raw-SQL writers set `updated_at`
  explicitly. ⚠️ If a future raw `UPDATE data_entries ...` omits `updated_at`, that
  column will go stale — re-introduce the trigger if that ever happens.
- **`carbon_projects` partial unique indexes** `uq_carbon_projects_unit_type_nonplan`
  (`ff4f9bac0339`), `uq_carbon_projects_unit_plan_name` (`6e32aa42f6f4`) and
  `uq_carbon_projects_unit_explore_creator` (`095d98bc390c`, explore sandboxes are no
  longer unique per creator).
- **`uq_emission_recalc_active`**, split into the `_unscoped` / `_scoped` pair
  (`3f254df7a368`).
- **`carbon_projects.is_grant_proposal`** column, derived from the grant report
  since `277bf6757926` (`uq_carbon_reports_project_grant`).

## Data migrations / backfills — not part of schema

Ignored on collapse: each collapse ships with a DB drop, so there are no old rows to
rewrite.

- 2026-06-15 collapse: `backfill_carbon_project_id`,
  `DELETE FROM year_configuration WHERE provider <> 'DEFAULT'`, `migrate_data_ingestion`.
- #2211 collapse: `strip_legacy_primary_factor_id_and_null_`,
  `strip_legacy_status_from_entry_json`, `backfill_data_entries_year_and_unit_id_`,
  `migrate_mice_research_facility_type_to_`, `migrate_legacy_traveler_sentinels_to_1_`,
  `rename_process_emissions_quantity_to_quantity_kg` (with its round-trip test).
- #2904 collapse: the `is_grant_proposal` guard in `277bf6757926`,
  `delete_orphaned_null_created_by_explore_` (`95fe938000d4`, #2458, with its test in
  `test_alembic_migrations.py`), and the `data_entry_emissions` backfill `UPDATE` in
  `1a9837dd65a3`.
