---
status: in-progress
issue: 2025
last_updated: 2026-08-18
title: "Process Emissions: rename quantity -> quantity_kg (doc-driven schema change)"
summary: "The data manager renamed the process-emissions quantity column to quantity_kg in the data-description doc and the SharePoint data/test/template files (issue #2025, 2026-08-17); the backend DTO, the served frontend template, and stored entry JSON still say quantity, so the current backoffice data upload fails every row. Rename end-to-end with a guarded jsonb data migration — no aliases, no dual-path."
---

# Process Emissions: rename `quantity` → `quantity_kg`

## Problem

Issue #2025 asked for the metric unit in the process-emissions template
header. Per the process that #1489 formalizes (data changes start with the
data manager), @martina-gallato already delivered the data side on
2026-08-17: the [data-description doc](https://epfl-enac.github.io/co2-calculator-back-office-doc/data-description)
and the SharePoint `data`/`test`/`template` files (`input_data_v2.12.5_2026-08-11`)
now all use **`quantity_kg`**. Her comment on the issue: "implementations
from your side are needed"; @charlottegiseleweil assigned the code side to
@pierreleripoll.

The code still uses `quantity` everywhere, which breaks in three ways:

1. **The backoffice per-year upload of the current
   `processemissions_data.csv` fails every row.** CSV columns are matched
   by exact DTO field name: `_get_expected_columns_from_handlers`
   (`backend/app/services/data_ingestion/base_csv_provider.py:135`) builds
   the accepted set from `create_dto.model_fields.keys()`, and
   `_process_row` drops anything else (`base_csv_provider.py:1228`). A
   `quantity_kg` column is silently discarded; the per-year path only
   hard-requires `unit_institutional_id`
   (`csv_providers/module_per_year.py:111`), so each row reaches
   `validate_create` without `quantity` and fails pydantic validation.
2. **The served template teaches users the old name.**
   `frontend/public/templates/processemissions_template.csv` still has
   header `category,subcategory,quantity,note` (with the UTF-8 BOM from
   #2069). It disagrees with the doc and with the SharePoint template.
3. **The header carries no unit** — the original #2025 complaint. The UI
   form already shows "Quantity (kg)" / "Quantité (kg)"
   (`frontend/src/i18n/process_emissions.ts:77`); only the CSV header
   lacks it.

The rename is not code-only: the CSV column name is also the **storage
key**. `DataEntryPayloadMixin.unflatten_payload`
(`backend/app/schemas/data_entry.py:37-48`) copies payload keys verbatim
into `data_entries.data`, and the emission formula reads
`ctx.get("quantity")` (`backend/app/modules/process_emissions/handlers.py:84`)
with a SQL-level access `DataEntry.data["quantity"].as_float()`
(`handlers.py:37`). Deployed DBs persist across deploys and hold
user-entered process-emissions rows (e.g. the #2072 report is a user
adding CH4/12kg in Explorer), so renaming the code without migrating the
JSON keys would make every existing entry silently stop computing — the
exact failure mode the guardrails rank worst.

## Prior art (reference commits)

The design copies decisions already made in this repo's history rather than
inventing new ones. Verbatim sources:

- **`f0e6fa28` — Guilbert Pierre, 2026-07-16 —
  `refactor(simulator-plan): rename percentage_of_last_year ->
percentage_of_reference_year (#1556)`.** The same shape as this change (a
  `DataEntry.data` JSON key rename), shipped _without_ a migration. The
  commit body states the checklist that justified skipping it: "Rename the
  DataEntry.data JSON key across the emission service, prefill, and tests
  **(planner-only key, no frontend usage, no production data)**. […] 68
  tests pass." We fail that checklist (frontend usage + deployed rows), so
  this change _does_ carry a migration — same rule, opposite conclusion.
- **`5293bbd5` — Guilbert Pierre, 2026-07-06 —
  `refactor(1661): remove primary_factor_id from DataEntry.data — factors
are derived state`.** Introduced the data-only migration
  `954eac6c95da_strip_legacy_primary_factor_id_and_null_.py`, whose
  docstring is the template for ours: "Data-only migration (plan 1661,
  v1.0 follow-up — **the DB persists across deploys now, so rows written
  before the primary_factor_id removal must be cleaned in place instead of
  waiting for a reseed that no longer happens**)". Patterns adopted:
  hand-written jsonb `op.execute` body, idempotency guard
  (`WHERE data::jsonb ? '<key>'`), and a downgrade policy that must be
  _stated_ (there: justified no-op, because the stripped values were dead).
- **`742cb939` — Benjamin, 2026-07-22 —
  `chore(db): Rename mice facility type to rodent (#866)`** (migration
  `2c7f5cf1c9de`). The reversible variant: a jsonb rewrite whose
  `downgrade()` is documented as "Restore `mice` — **the exact
  inverse**". Our rename is losslessly reversible, so we adopt this
  downgrade style rather than 954eac's no-op.
- **`33520d0f` — Guilbert Pierre, 2026-08-11 —
  `refactor(purchase): rename Additional purchases to Centralized
purchases (#1859) (#2066)`.** Template for the full-stack breadth of a
  rename PR: backend DTOs + frontend module-config/components + i18n in
  one reviewable change.
- **Issue #2025 thread (the mandate).** charlottegiseleweil, 2026-08-08:
  "C'est une modif sur les données, donc à faire par @martina-gallato qui
  nous informe ensuite (ici) lorsque c'est à jour dans la doc et dans les
  données template pour qu'on mette à jour à notre tour."
  martina-gallato, 2026-08-17: "a column in the data, test and template
  has changed from `quantity` to `quantity_kg` — the data doc and the
  files in the data input are up to date now. **implementations from your
  side are needed**." charlottegiseleweil, 2026-08-17: "@pierreleripoll
  du coup tu pourrais mettre à jour le data scheme juste avant de faire
  #1489 justement ?" — the maintainer-side green light this plan executes.

## Design

Full rename, one PR, no compatibility path (guardrail: "when the new way
ships, delete the old way in the same PR"). The methodology is lifted from
the prior-art commits below: code+tests+migration reviewed as one story,
migration guarded for idempotency, downgrade an exact inverse.

### Backend

- `backend/app/modules/process_emissions/data_entries.py`: rename
  `quantity` → `quantity_kg` on `ProcessEmissionsHandlerCreate`,
  `ProcessEmissionsHandlerUpdate`, `ProcessEmissionsHandlerResponse`, and
  the two `validate_quantity` field validators. Column derivation is
  automatic from the DTO, so both CSV paths accept `quantity_kg` with no
  ingestion-layer change.
- `backend/app/modules/process_emissions/handlers.py`: the sort/filter
  map `DataEntry.data["quantity"].as_float()` (line 37) and the formula
  `ctx.get("quantity")` (line 84) → `quantity_kg`.
- `backend/app/core/data_entry_permissions.py:121`: the #951 per-dataset
  edit-rights map lists the USER-editable fields per module; process
  emissions must list `quantity_kg` or the field becomes read-only in the
  UI. Purchase (`:223`) and energy combustion (`:129`) keep their own
  `quantity` — different modules, unchanged DTOs.
- `backend/app/seed/random_generator/seed_data_entries.py:404`:
  `build_process_emissions()` emits the entry `data` dict directly, so it
  has to write the new key or seeded rows fail response validation.
- **Alembic data migration** (generated via `make db-revision`, body
  hand-written like every data-only migration in
  `backend/alembic/versions/`):

  ```sql
  -- upgrade: idempotent (the `? 'quantity'` guard makes re-runs no-ops)
  UPDATE data_entries
  SET data = (data::jsonb - 'quantity'
              || jsonb_build_object('quantity_kg', data::jsonb -> 'quantity'))::json
  WHERE data_entry_type_id = 50
    AND data::jsonb ? 'quantity';
  -- downgrade: exact inverse (quantity_kg -> quantity), same guard
  ```

  Scoped to `data_entry_type_id = 50` (process_emissions) — other modules
  legitimately keep their own `quantity` fields (purchase, energy
  combustion). Emission _values_ are unchanged, so no recalculation is
  required after the migration.

  The two statements are module-level constants (`UPGRADE_SQL` /
  `DOWNGRADE_SQL`) rather than inline strings, so the round-trip test can
  execute the exact shipped SQL instead of a copy that drifts.

### Frontend

- `frontend/src/constant/module-config/process_emissions.ts:48-59`: field
  `id: 'quantity'` → `'quantity_kg'`, `labelKey` →
  `${MODULES.ProcessEmissions}.inputs.quantity_kg`.
- `frontend/src/i18n/process_emissions.ts:77`: rename the key to
  `.inputs.quantity_kg` (label text stays "Quantity (kg)" / "Quantité
  (kg)"; en + fr live in the same file).
- `frontend/src/components/organisms/module/ModuleTable.vue:1878`: the
  ProcessEmissions branch `baseRequired = ['category', 'quantity']` →
  `'quantity_kg'`. Do **not** touch the purchase (`:1821`) or
  energy-combustion (`:1895`) `'quantity'` entries — different modules,
  unchanged DTOs.
- `frontend/public/templates/processemissions_template.csv`: header →
  `category,subcategory,quantity_kg,note`. Preserve the UTF-8 BOM (#2069)
  and the prefilled category scaffold rows.

### Docs

- `docs/src/backend/csv-seed-formats/inventory.md`: the
  `processemissions_data.csv` and `processemissions_test.csv` rows still
  document `quantity`; update to `quantity_kg`.

## Test plan

Every change ships with a test on the side it touches:

- **Backend regression (the bug):** extend the process_emissions spec in
  `backend/tests/integration/services/data_ingestion/test_csv_ingest_matrix_pg.py:129`
  to ingest a `quantity_kg`-headed CSV and assert the entry lands with
  `data["quantity_kg"]` and a computed emission. Add a case asserting a
  legacy `quantity`-headed CSV now records a per-row validation error
  (visible failure, not a silent drop).
- **Backend unit:** DTO validator tests (negative `quantity_kg` rejected;
  required on create, optional on update).
- **Migration:**
  `tests/integration/services/data_ingestion/test_quantity_kg_migration_pg.py`
  seeds a det-50 row with the old key plus a det-61 control row, runs
  `UPGRADE_SQL`, and asserts the rename, the preserved value, the
  untouched control row, idempotency on re-run, and an exact-inverse
  downgrade. Verified falsifiable: dropping the `? 'quantity'` guard fails
  the idempotency assertion.

  It imports the statements from the revision module and runs them on the
  data_ingestion testcontainer rather than driving `alembic upgrade` in a
  subprocess. `scripts/manage_db.py` and `alembic/env.py` both resolve the
  target DB from `settings.DB_URL`, and
  `Settings.settings_customise_sources` (`app/core/config.py:359-370`)
  deliberately ranks `.env` **above** real env vars — so a
  subprocess-driven migration test ignores the DSN it is handed and acts on
  whatever `backend/.env` points at, i.e. the developer's own database. See
  the note in _Out of scope_.

- **Existing-test fallout** (same rename; other modules' fixtures left
  alone): `tests/unit/core/test_data_entry_permissions.py`,
  `tests/unit/repositories/test_data_entry_repo.py`,
  `tests/unit/services/test_data_entry_emission_service.py`,
  `tests/unit/services/test_simulator_plan_service.py`,
  `tests/unit/services/test_simulator_plan_reference_year_perf.py`,
  `tests/integration/services/data_ingestion/test_strategy_a_rematch_pg.py`,
  and the `process_emissions_smoke.csv` fixture header.
- **Frontend:** existing process-emissions Playwright coverage must pass
  with the renamed field id; manual check that create/edit round-trips and
  charts update.

## Out of scope

- `quantity` fields of other modules (purchase, energy combustion) — not
  renamed by the data manager, unchanged.
- A generic CSV column-alias mechanism — rejected in favor of the clean
  rename (no dual-path).
- The systematic doc-vs-code audit — that is #1489; this plan is its
  first exercised instance and the `sed`-able model for future `[DATA]`
  renames.
- **Making `tests/integration/test_alembic_migrations.py` safe to run
  locally.** Found while building the migration test, and confirmed by
  losing the local dev DB to it: because `.env` outranks env vars, its
  `manage_db --action drop` runs `DROP DATABASE … WITH (FORCE)` against
  whatever `backend/.env`'s `DB_URL` names, not the throwaway container it
  sets up. Harmless in CI (no `.env` there), destructive on a developer
  machine. Out of scope here — worth its own issue; the fix is probably
  passing `--db-name` explicitly and giving `alembic/env.py` a DSN
  override the settings precedence cannot shadow.
- Frontend validation coverage: no frontend test asserts process-emissions
  field rules today (the one fixture naming the module mocks permissions,
  not fields). Adding it is deliverable (2) of #1489.
