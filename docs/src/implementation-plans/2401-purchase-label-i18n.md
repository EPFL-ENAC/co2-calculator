---
status: in-progress
issue: 2401
last_updated: 2026-08-31
title: "Classification label i18n: translation table + generic CSV convention, equipment + purchase"
summary: "Adds a (field_name, value, lang) translation table (proposition 2) fed by a generic <field>_<lang> CSV column convention, wires the taxonomy tree builder AND the submodule search filter (#2516) to serve/match localized labels per request. Ships against equipment and purchase; other modules (buildings, headcount, research_facilities, external_cloud_and_ai, process_emissions — per charlottegiseleweil's field list on the issue) pick it up by adding the suffixed CSV column, no further backend code change for the self-labeling shape."
---

## Decision (team, #2401)

Proposition 2 — a normalized translation table — over wide columns, JSONB,
or frontend-owned translations. Ingestion convention (Teams call,
guilbep + domq, 2026-08-31): the base CSV column is English, a `_fr` suffix
column is the French translation; a blank cell or missing column means no
translation for that row and the typeahead/table falls back to English.
This **supersedes** the issue body's "half-translated ingest fails loudly"
line — the team's later decision is the one implemented.

```csv
equipment_category,equipment_class,equipment_class_fr,sub_class,sub_class_fr,active_usage_hours_per_week,standby_usage_hours_per_week,active_power_w,standby_power_w,ef_kg_co2eq_per_kwh
scientific,Engine,Moteurs,Large Motor/Generator,Gros moteur/Générateur,42,126,12000.0,0.0,0.097
```

## Root cause this also fixes

Audited every module's classification label path before building (branch:
`fix/2401-i18n-in-table`). Only two modules ever had bilingual classification
data:

- **equipment**: `i18n/equipment_factors.ts` (1654 lines) — dead. The
  taxonomy node's `translation_key` is the raw CSV value (`"Power
supplies"`), but the file's keys are prefixed slugs
  (`equipment_factor_power_supplies`); `$te()` never matches, so every
  equipment class/subclass has always rendered in English regardless of
  locale. Nothing else references the file by key.
- **purchase**: `i18n/purchase_factors.ts` (89k lines) — works, by
  coincidence: its keys are the raw UNSPSC code, which is exactly what
  `translation_key` carries for purchase. This is the file #2391 decision 4
  already plans to delete once purchase's server-side typeahead ships.

Every other module (buildings, headcount, research_facilities,
process_emissions, external_cloud_and_ai, professional_travel) has never had
a translation source at all — raw value shown regardless of locale.

## Schema

`classification_translations(field_name, value, lang) -> label`, composite
PK, year-independent (labels don't vary by year, unlike the `factors` rows
they annotate). `field_name` disambiguates which classification column a
value belongs to (a `domq` review point) — the same string under two
different fields is two different translations.

Two shapes a handler can carry, both served by the same table and the same
lookup:

1. **Self-labeling field** (equipment `equipment_class`/`sub_class`,
   buildings `room_type`, external_cloud_and_ai `usage_type`/`service_type`,
   process_emissions `category`/`subcategory`, research_facilities
   `researchfacility_type`): the classification value itself _is_ the
   English label. Translated by a row keyed on `(kind_field, kind_value)` /
   `(subkind_field, subkind_value)`.
2. **Code + separate label field** (purchase: `kind_field =
purchase_institutional_code` is an opaque UNSPSC code;
   `kind_label_field` points at the description column that actually holds
   the text). Translated by a row keyed on `(kind_label_field,
english_description)` instead — the code itself is never a translation
   key.

`professional_travel`'s `category`/`cabin_class` carry no translation by
team decision (short codes, not natural-language labels) — no `_fr` column,
no rows, unaffected.

English needs no round trip and no rows: `lang="en"` skips the translation
query entirely and uses the existing `to_label`/`kind_label_field` path
unchanged.

## Ingestion

`BaseFactorCSVProvider._collect_translations` (generic, not equipment-
specific): for every field in `handler.classification_fields` that has a
non-blank value on a row, checks for a `f"{field}_fr"` column and stashes
`(field, value, "fr") -> label` if present and non-blank. Upserted once per
job (`ON CONFLICT (field_name, value, lang) DO UPDATE`), in the same
transaction as the factor batch — a translation never lands without the
factors it labels.

Any handler whose CSV grows a `<classification_field>_fr` column gets
translation support with zero code change — the mechanism is generic over
`classification_fields`, per the team's "general-purpose, not equipment-
only" decision (domq's review comment). Equipment
(`equipment_class_fr`/`sub_class_fr`) and purchase
(`purchase_institutional_description_fr`, added to
`purchase_common_classification_fields` and `PurchaseModuleHandler.
kind_label_field` in this PR) both ship. `purchase_institutional_description`
is the pre-existing institutional-CSV column name (confirmed in
`docs/src/backend/csv-seed-formats/inventory.md` and the original #2401
issue text) — not invented for this change.

## Search filter (#2516)

The same table backs `GET .../modules/{module}/{submodule}`'s `filter`
query param (root cause of #2516: "search on class" found nothing in
French because the filter only ever `ILIKE`d the stored English value).
`DataEntryRepository._filter_conditions` now ORs in an
`IN (SELECT value FROM classification_translations WHERE field_name=...
AND lang=... AND label ILIKE :pattern)` per translatable `filter_map`
column, alongside the existing raw-column `ILIKE` (never replacing it —
an English term must keep matching regardless of locale, which is also
the fallback for a value with no translation row). Both handler shapes
are covered. The self-labeling shape (`kind_field`/`subkind_field` —
equipment's `equipment_class`/`sub_class`) matches the translated-label
subquery directly on the filtered column. The code + label-field shape
(purchase — added 2026-08-31 after live testing, initially deferred) hops
through `factors.classification`: the filtered column holds an opaque
code, so the condition is `code IN (SELECT the factor's code WHERE its
description ILIKEs the term — English — OR its description IN the
translated-label subquery — request locale)`. That also makes the
_English_ description searchable, which never worked either (the
description isn't stored on the entry). The factor subquery is
deliberately unscoped by det/year — only the module's own factors carry
the label key; scope it if it ever shows up in profiles. Threaded through
`get_submodule` (new `lang` query param) -> `DataEntryService.
get_submodule_data` -> `DataEntryRepository.get_submodule_data`, all three
call sites that build filter conditions (`_page_first_entry_ids`, the main
statement, the count statement) via the one shared `_filter_conditions`
helper — a single source of truth so the page-first optimization and the
original-shape path can never disagree on which rows match.

## Serving

`ModuleHandlerService.get_taxonomy_with_etag` takes a `lang` param
(`"fr-CH"` etc., normalized to a short code; anything not in
`TRANSLATABLE_LANGS = ("fr",)` falls back to `"en"`). The tree cache key
becomes `(data_entry_type, year, lang)`; write-time invalidation
(`taxonomy_cache.clear()`) already drops the whole cache regardless of key
shape, so this is safe without touching the broadcast/invalidation path.

`GET /taxonomies/module/{module}/{data_entry}` and the batch route both
gain a `lang` query param (default `"en"`) — chosen over `Accept-Language`
so the value is part of the cached URL and the existing `Cache-Control`
(`max-age=86400` once a year is started) needs no `Vary` header.

Frontend: `api/taxonomies.ts` sends `lang=<short locale>` derived from
`i18n.global.locale.value`; `stores/factors.ts`'s per-`(submodule, year)`
cache key gained the locale too, so a language switch mid-session doesn't
serve a minute-old tree in the wrong language.

Found live-testing (2026-08-31): a third taxonomy call site,
`stores/modules.ts` `getSubmoduleTaxonomy` (the single-entry path
`ModuleTable` uses when one submodule expands), hand-built its URL inside
the store with only `?year=` and never sent `lang` — so the table's
labels stayed English while the batch path localized fine. Now routed
through `getDataEntryTaxonomy`; pinned by the CT regression test
`tests/unit/taxonomy-lang.spec.ts` (`fr-CH` locale → `lang=fr` on the
request). Note the table _rows_ endpoint intentionally keeps raw stored
values in every locale — `lang` there only widens `filter=` matching
(#2516); display labels come from the taxonomy.

Also found live-testing: the purchase taxonomy 500'd (every lang) on the
81 real factor rows whose `purchase_institutional_description` is blank —
`classification.get(label_field, kind_value)` only defaults on a _missing_
key, so a present-but-`None` description built a `label=None` node and
failed `TaxonomyNode` validation. Both label-field branches now fall back
to the code explicitly when the label is blank (what pre-#2401 users saw
for those rows); regression test parametrized over en/fr in
`tests/unit/services/test_classification_translation_labels.py`.

Third live-testing find (2026-08-31): with a table open, a navbar
language switch never refetched it — rows kept the previous locale's
labels until re-expand. The module store now records each submodule's
last fetch args (rows and taxonomy, batch included) and replays every
_loaded_ one when the i18n locale changes; CT regression test
`tests/unit/locale-refetch.spec.ts`.

Suites run 2026-09-01 (local): backend unit 2547 passed; integration
461 passed / 2 skipped, plus the new `_pg` translation-stack file — the
one remaining failure (`test_building_rooms_csv_unknown_room_is_rejected_
as_row_error`) is pre-existing on `dev`: its registered fixture
`tests/fixtures/csv/building_rooms_unknown_room.csv` was never committed
(#2253 follow-up, not this branch). Frontend CT 588 passed, e2e passed
(3 pre-existing skips). Locust smoke (20 users, ModuleReadUser, dev
server): no errors, table endpoint p50 140 ms.

**Row-level labels (2026-08-31, maintainer decision).** Live testing
surfaced that the table's display path was still frontend-owned for
purchase: `ModuleTable`'s label map prefers `$te(<code>)` — the 89k-line
`purchase_factors.ts` — over the backend's `node.label`, and feeding it at
all means fetching the ~17.7k-node purchase taxonomy per table view. The
taxonomy is for _form options_ (its actual job); table rows now carry
their own display text instead: every submodule item gains an optional
`labels: {field: label}` map (`DataEntryRepository._row_labels`), built
per page from the already-joined resolved factor (code + label-field
shape: translated description, English description, or bare code — same
fallback chain as the taxonomy builder) plus one batched
translation-table query for self-labeling fields (`labels` present only
when a translation row exists; English self-labeling rows need nothing).
`ModuleTable` renders `row.labels[field] ?? taxonomyMap[value] ?? value`
(`utils/classificationLabels.ts`); `PrintModuleTable` keeps its map (it
falls through to the backend-localized `node.label`).

**`equipment_factors.ts` and `purchase_factors.ts` are deleted.** The
equipment file was dead (audit above) and its content now lives in the
uploaded CSV's `_fr` columns; the purchase file is superseded — table
cells read `row.labels`, and form/inline selects fall through the (now
always-missing) `$te` check to the backend-localized `taxoOptNode.label`.
The i18n index globs the folder, so both locales dropped them together.

## Deliberately out of scope here

- **`translation_key` machinery** (#2401's "also in scope" section): left
  wired but inert for equipment. Untangling its four Vue call sites wants
  its own change + CT test (per the #2391 plan, which deferred the same
  thing) — verifying `$te(opt.value)` isn't live for some _other_ module
  first (e.g. emission-taxonomy enum values like `domestic_waste`) is real
  work on its own.
- ~~**Purchase server-side typeahead**~~ — delivered later the same day on
  this same branch after the maintainer pulled it in: see #2391's plan
  (decision 4) for the record. Purchase pages no longer download the
  taxonomy tree anywhere.
- **Headcount** (`sius_code_name`/`_fr`, per charlottegiseleweil's list):
  headcount's handlers set `kind_field = None` — they never go through
  `get_taxonomy_with_etag` at all; `sius_code` labels are consumed
  directly by `PlannerHeadcountRows.vue` off `i18n/headcount_factor.ts`.
  Bringing headcount onto this table needs that component switched to a
  DB-backed lookup, not just a CSV column — separate follow-up.
- **buildings/research_facilities/external_cloud_and_ai/process_emissions**
  `_fr` columns (per charlottegiseleweil's list): the self-labeling-shape
  mechanism already supports every one of them (their `kind_field`/
  `subkind_field` values match the columns she listed) — no code change
  needed, only an operator uploading a CSV with the suffixed column. Not
  exercised by a test here since no such CSV exists yet; the equipment
  tests cover the identical code path.
- **Alphabetical sort by localized label** (`get_taxonomy_with_etag` builds
  children in factor-row order, unsorted) — possibly the actual mechanism
  behind #2505 ("Alphabetic sort" bug), not requested on this issue; noted
  for whoever picks that one up.

## Verification (2026-08-31, local Docker session)

Both handoff steps from the sandbox session are done:

- **Migration**: `make db-revision` against a scratch Postgres migrated to
  head `95fe938000d4` autogenerated exactly the hand-authored shape — same
  table, same four `AutoString` columns and lengths, same 3-column
  composite PK, and no false-positive `drop_index` noise at all. The
  generated file
  (`2026_08_31_1805-42aecc9a8a5b_add_classification_translations_table.py`)
  replaces the hand-authored `b3d9a7e5c1f2` one. Upgrade → downgrade →
  upgrade cycles cleanly, and
  `tests/integration/test_alembic_migrations.py` passes (2/2, in its own
  `postgres:16-alpine` container).
- **Frontend type-check**: `make type-check` (vue-tsc via
  `tsconfig.typecheck.json`, Node 26.5) passes. `make ci` green after a
  ruff-format fix on one new test file and a prettier pass on two plan
  docs.
- ERD regenerated (`make erd`) so `classification_translations` shows in
  `docs/src/database/erd.md`.

Gotcha (re-)confirmed on the way: `backend/.env` wins over injected env
vars in this repo, so an active `DB_URL` there hijacks the DSN the
migration test passes to its `manage_db` / `alembic` subprocesses — they
then drop/create/migrate the `.env` database instead of the
testcontainer's. Full `uv run pytest tests/` was deliberately **not** run
with a local `DB_URL` active for that reason (it would wipe the local
`co2_calculator` DB); PR CI covers the full suite with no `.env` present.

## Delivery checklist

- [x] `classification_translations` table + model (migration autogenerated
      via `make db-revision`, verified — see Verification above)
- [x] `ClassificationTranslationRepository` (upsert, `get_labels`)
- [x] Generic `<field>_<lang>` CSV collection in
      `BaseFactorCSVProvider`, upserted in the same transaction as the
      factor batch
- [x] `ModuleHandlerService.get_taxonomy_with_etag` locale-aware labeling,
      both handler shapes (self-labeling field, code + label field)
- [x] `lang` threaded through both taxonomy routes, frontend API calls, and
      the frontend factors-store cache key
- [x] Purchase: `purchase_institutional_description` added to
      `purchase_common_classification_fields` + the factor DTOs;
      `PurchaseModuleHandler.kind_label_field` set — the code+label-field
      shape now resolves through the same generic mechanism
- [x] Search filter (#2516): `lang` threaded through `get_submodule` ->
      `DataEntryService`/`DataEntryRepository.get_submodule_data`; one
      shared `_filter_conditions` helper used by all three query sites
      (page-first ids, main statement, count)
- [x] Purchase search by description (2026-08-31, was deferred; done after
      live testing): the code + label-field shape hops through
      `factors.classification`, matching the English description and the
      translated label; regression tests in
      `tests/unit/repositories/test_submodule_filter_translation.py`
- [x] Row-level labels (2026-08-31): submodule items carry an optional
      `labels` map built from the resolved factor + one batched
      translation query; `ModuleTable` renders it first
      (`utils/classificationLabels.ts`) — the purchase table no longer
      depends on the taxonomy for display. Tests in the same repo test
      file + `frontend/tests/unit/classification-labels.spec.ts`
- [x] `i18n/equipment_factors.ts` and `i18n/purchase_factors.ts` deleted
      (2026-08-31) — backend labels supersede both; forms fall through to
      the backend-localized `taxoOptNode.label`
- [x] Unit tests: CSV collection (blank cell, missing column, null
      classification value), taxonomy label resolution (English skips the
      query, French translates, untranslated falls back, `fr-CH`
      normalizes, `kind_label_field` shape), search filter (French term
      matches translated label, untranslated value falls back to English
      match, English locale doesn't leak French matches)
- [x] Verify the migration against a real DB; run `make type-check`
      (2026-08-31 local session — see Verification above)
- [x] Seed CSVs backfilled with `_fr` columns from the frontend i18n files
      (2026-08-31, operator `INPUT_DATA` v2.12.5 folder, outside the repo):
      `equipment_factors.csv` — `equipment_class_fr` 206/206,
      `sub_class_fr` 114 (the other 92 rows have a blank `sub_class`);
      `purchases_common_factors.csv` —
      `purchase_institutional_description_fr` 17598/17679 (the 81 blanks
      also have a blank English description). Matching was by i18n key
      first (the raw CSV value, typos included — mirroring the old
      `$te(<value>)` lookup), then by English value; zero non-empty values
      left untranslated. Operator upload still pending once merged.

## References

- #2391 decision 4 (parks purchase's own ingestion columns here);
  `docs/src/implementation-plans/2391-factor-option-delivery-rewrite.md`
- #2396 (deferred `translation_key` untangling, same reasoning applies here)
