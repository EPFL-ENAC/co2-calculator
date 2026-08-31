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
   `researchfacility_type`): the classification value itself *is* the
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
the fallback for a value with no translation row). Scoped to the
self-labeling shape only (`kind_field`/`subkind_field` — equipment's
`equipment_class`/`sub_class`): the code + label-field shape (purchase's
`purchase_institutional_code`) would need a join through
`factors.classification` to map a translated description back to its
code, which this PR doesn't add — searching purchase by a translated
description is a follow-up, tracked below. Threaded through
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

**No Vue component changes.** `ModuleForm.vue`, `ModuleInlineSelect.vue`,
`ModuleTable.vue`, and `PrintModuleTable.vue` already fall through
`translation_key`/`$te(opt.value)` (both dead, per the audit above) to
`taxoOptNode.label` — the exact field the backend now serves localized.
Fixing the label at the source fixes every consumer for free.

## Deliberately out of scope here

- **`translation_key` machinery** (#2401's "also in scope" section): left
  wired but inert for equipment. Untangling its four Vue call sites wants
  its own change + CT test (per the #2391 plan, which deferred the same
  thing) — verifying `$te(opt.value)` isn't live for some *other* module
  first (e.g. emission-taxonomy enum values like `domestic_waste`) is real
  work on its own.
- **`equipment_factors.ts` / `purchase_factors.ts` deletion**: kept.
  `equipment_factors.ts` is the natural backfill source for the CSV's `_fr`
  column until an operator re-uploads one; `purchase_factors.ts` deletion
  is #2391 decision 4's remaining job (the server-side typeahead itself),
  now that the label plumbing it was blocked on has landed.
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
- **Purchase search by translated description** (`filter=ordinateur&lang=fr`
  matching a row whose `purchase_institutional_code` resolves to an
  English description containing "computer"): needs a join through
  `factors.classification` the search filter doesn't have — see the
  "Search filter" section above. Today it silently matches nothing extra
  for purchase (safe, not wrong), same as before this PR.
- **Alphabetical sort by localized label** (`get_taxonomy_with_etag` builds
  children in factor-row order, unsorted) — possibly the actual mechanism
  behind #2505 ("Alphabetic sort" bug), not requested on this issue; noted
  for whoever picks that one up.

## Verification gap (this sandbox)

No Docker/Postgres access here: the Alembic migration
(`2026_08_31_1800-b3d9a7e5c1f2_add_classification_translations_table.py`)
was hand-authored (mirrors `year_configuration`'s composite-PK shape from
the initial migration) rather than generated via
`make db-revision message="..."`, and `vue-tsc` couldn't run (worktree has
no installed `node_modules`, and the sandbox's Node 24 is below the
project's required `>=26`). **Before merging**: run `make db-revision` /
`make test-migrations` against a real DB to confirm the autogenerated diff
matches (or replace) this migration, and run `make type-check` on the
frontend.

### Handoff: what a Docker-capable session should do

Branch `fix/2401-i18n-in-table`, PR
[#2583](https://github.com/EPFL-ENAC/co2-calculator/pull/2583) (draft),
already pushed to `origin`. Two verification steps left, both blocked by
this sandbox's Docker/Node access:

1. **Regenerate/verify the migration.**
   ```
   make run-db
   cd backend && make db-revision message="add classification_translations table"
   ```
   Compare the autogenerated file against
   `backend/alembic/versions/2026_08_31_1800-b3d9a7e5c1f2_add_classification_translations_table.py`
   (a single `op.create_table("classification_translations", ...)` with a
   3-column composite PK `(field_name, value, lang)`, no indexes beyond
   the PK). If it matches in substance, delete the hand-authored file and
   commit the generated one instead (keep the same
   `YYYY_MM_DD_HHMM-<hash>-<slug>.py` naming convention, and re-point
   `down_revision` at whatever the real current head is — it may have
   moved since `95fe938000d4`). Per the guardrails, autogenerate may also
   propose unrelated `drop_index` calls against tables this PR never
   touched — prune those, they're a known false-positive pattern in this
   repo, not something this PR caused.
   Then run `cd backend && make test-migrations` (spins up its own
   `postgres:16-alpine` testcontainer) to confirm `alembic upgrade head`
   applies cleanly end to end.

2. **Frontend type-check.**
   ```
   cd frontend && npm ci && make type-check
   ```
   (root `make type-check`, not a bare `tsc` — this is a Vue project, see
   `vue-tsc --noEmit -p tsconfig.typecheck.json`). Files most likely to
   surface an issue if something's off: `frontend/src/api/taxonomies.ts`,
   `frontend/src/stores/factors.ts`, `frontend/src/stores/modules.ts` (all
   three import `i18n` from `@/boot/i18n` and were never run through the
   real compiler in this sandbox — no `node_modules` installed, and the
   sandbox's Node 24 is below the project's required `>=26` so `npm ci`
   itself refused to run there).

Also run `make ci` (lint + type-check, backend + frontend) and
`uv run pytest tests/` (full suite, not just `tests/unit`) once a DB is
available — this sandbox only ran `tests/unit`, which passes with the same
6 pre-existing/DB-less failures as `dev` (unrelated: `test_audit.py`,
`test_files_*.py`, `test_unit_auth.py` — all need a real Postgres).
Nothing in this PR touches those files.

Everything else (design decisions, what's in/out of scope, the search-filter
root cause for #2516) is above in this same doc — that's the full context,
no need to re-derive it from the issue thread.

## Delivery checklist

- [x] `classification_translations` table + model (hand-authored migration,
      see verification gap above)
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
- [x] Unit tests: CSV collection (blank cell, missing column, null
      classification value), taxonomy label resolution (English skips the
      query, French translates, untranslated falls back, `fr-CH`
      normalizes, `kind_label_field` shape), search filter (French term
      matches translated label, untranslated value falls back to English
      match, English locale doesn't leak French matches)
- [ ] Verify the migration against a real DB; run `make type-check`
      (blocked in this sandbox — see above)
- [ ] Equipment factor CSV template/seed data gets `equipment_class_fr` /
      `sub_class_fr` columns populated (backfill from `equipment_factors.ts`)
      so the feature has real data once merged

## References

- #2391 decision 4 (parks purchase's own ingestion columns here);
  `docs/src/implementation-plans/2391-factor-option-delivery-rewrite.md`
- #2396 (deferred `translation_key` untangling, same reasoning applies here)
