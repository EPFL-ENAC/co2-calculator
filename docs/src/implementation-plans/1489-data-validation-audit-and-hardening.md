---
issue: 1489
status: in-progress
last_updated: 2026-08-25
title: "Data-validation audit and hardening — backend as single source of truth"
summary:
  "Slice 1 of #1489: a systematic audit of every documented data rule (back-office
  doc site, data-description pages) against actual backend enforcement, frontend
  enforcement, and test coverage, across the four ingestion paths (back-office
  reference/factor CSVs, entry CSVs, direct form input, reduction-objective CSVs). Every claim was re-verified by
  probing the DTOs and replaying fixtures. Mismatches are classified code-gap or
  doc-stale (the latter handed to the data manager, not fixed in code), and the audit
  ends in an ordered set of small follow-up PRs, starting with the #1545 reference-CSV
  silent-wipe hole. The cross-repo doc-change automation bonus is parked."
---

# Data-validation audit (#1489)

## Reading guide — plain-language summary

> This section explains the document in plain language. The technical detail
> (tables A–E below) is the **evidence**; everything can be understood from
> this summary plus the follow-up table (section E).

### The starting problem

The [doc site](https://epfl-enac.github.io/co2-calculator-back-office-doc/data-description)
describes the rules for every piece of data (required field, value ≥ 0, exact
CSV column names…). Nobody had ever checked whether the code actually enforces
them. Bug #1545 showed it doesn't: one misspelled column
(`room_surface_square_meters`, one extra "s") **silently wiped the surface of
every room** while the job reported SUCCESS — and then nothing computed
anymore, with no error message anywhere.

### The key idea: 4 paths, not 200 fields

Data enters the app through **four paths**, each with its own validation code:

- **P1** — back-office CSVs (reference data + emission factors)
- **P2** — entry CSVs (bulk upload by users)
- **P3** — the web forms (day-to-day use)
- **P4** — reduction-objective CSVs

Almost every hole is a **path** hole: a path that ignores unknown columns
affects _every_ module that goes through it. P4 was the only well-built path
(every row validated, all errors reported, nothing persisted if any row is
bad) — the fixes copy that model, they invent nothing.

### What the audit found (the 4 examples that summarize everything)

1. **The typo that wipes a table** (#1545): unknown column → a warning in a
   log nobody reads → silent `NULL` → the whole table is replaced → SUCCESS
   reported. _(Fixed by #2216.)_
2. **"Validate… then throw it away"**: the factor upload validated every row
   then **discarded the result** and persisted the raw values — a number that
   arrived as text stayed text in the database. _(Fixed by #2231.)_
3. **Forms accept any field**: all 15 create schemas probed accept and store
   `typo_field_xyz: 42`. Worse: a key named `data` bypasses validation
   entirely. _(Still open — S5.)_
4. **Silence at compute time**: an entry that can't find its factor produced
   **nothing** instead of an error — this is what turns all the silent bad
   data into "my results disappeared". _(Being fixed via #2091 / #2050 /
   #1186.)_

Plus **8 cases where the doc is wrong**, not the code (section D, for
@martina-gallato) — e.g. the doc says `"1-5 times per day"` but the backend
stores `1_5` and rejects the label: a CSV written by following the doc fails.

### What is already fixed

- **#2216** (by @guilbep): unknown column in a reference CSV = hard error,
  before anything is wiped. → F-1 ✅
- **#2231** (merged, **v1.4.0**), 4 commits:
  1. animal facilities finally reject `use = -5` and empty ids;
  2. `"   "` (whitespace-only) is refused in every required string field,
     across all modules;
  3. the factor upload persists the **validated values** (classification stays
     hand-built — the 310B identity index depends on it), and `"12,5"` fails
     the upload instead of becoming NULL;
  4. the forms know the same rules as the backend (missing required/min/max)
     and whitespace-only counts as empty client-side.
- **#2291** (merged): a regression test pinning that accepted rows persist
  their DTO-normalized form (`"  CHF "` → `"chf"`) — the executable answer to
  "why keep the validator's return value".
- **#2307** (merged 2026-08-24, research-facilities manual input, by the lead):
  RF `use` and `use_unit` are now required in the form, and `use` is bounded per
  unit on both sides (`%` ≤ 100, `hours` ≤ 8736, `housings` integer-only) —
  closes the RF part of F-8 and adds one doc-stale row (D-8: the bounds are
  undocumented).

### What remains to be done

| What                         | In one sentence                                                                                                                                   | Blocked on                            |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| **Merge this PR**            | This document is the reference plan for #1489.                                                                                                    | review @guilbep                       |
| **S3**                       | Entry CSVs (P2) still silently ignore unknown columns — the `strict_column_validation` switch exists in the code but is enabled nowhere.          | go-ahead @guilbep (changes a default) |
| **S5**                       | Close the two form holes (invented fields stored, bypass via the `data` key), first promoting `percentage_of_reference_year` to a real field.     | sign-off @guilbep (permissions)       |
| **S7**                       | Contract test: the backend exports its rules as JSON, the frontend tests itself against them — parity can no longer drift.                        | simple ack                            |
| **S8**                       | Playwright tests against a real backend (= checkbox 2 of #1489).                                                                                  | parked — CI infra                     |
| **3 product questions**      | FE `min: 0.001` where the backend accepts 0; enforce integers client-side; F-13: the Explorer pre-fills `fte_count = 0`, which both sides reject. | product answer                        |
| **Section D → data manager** | Hand the 8 doc corrections to @martina-gallato.                                                                                                   | one comment on #1489                  |
| **#1545**                    | Covered by #2216 + #2231; to be closed once Martina confirms.                                                                                     | @martina-gallato                      |

---

**Reference spec:** the
[data-description pages](https://epfl-enac.github.io/co2-calculator-back-office-doc/data-description)
of the back-office doc. Per #1489 (superseding ADR-020/#1434), the **backend is the
single source of truth** for enforcement; the doc records intent. Where they disagree,
the mismatch is either a `code-gap` (backend behavior looks accidental) or `DOC-STALE`
(backend behavior is deliberate — comment, exemption, or pinning test — and the doc
must catch up; those go to the data manager, section D).

**Trigger:** #1545 — a typo'd column name in `building_rooms_reference.csv` NULLed the
surface of every room while the job reported SUCCESS, and nobody could tell why
results stopped computing.

**Method.** Every non-OK verdict below was re-verified on `dev` (at `d3caa0ac`) with
fresh evidence: `uv run python` probes feeding the Create DTOs bad payloads (unknown
key, out-of-range, wrong type, whitespace-only required string, client-supplied `data`
dict — all 15 module Create DTOs probed), a replay of the committed #1545 fixture
`backend/INPUT_DATA/building_rooms_reference_test_wrong_column_name.csv` through
`ReferenceDataCSVProvider._validate_headers`, and a green run of the relevant suites
(`uv run pytest tests/unit/modules/ tests/unit/services/data_ingestion/` — 433
passed). Probe scripts were throwaway (session scratchpad, not committed). The _Tests_
columns record rule-level test existence found by inspection, not mutation-verified
coverage.

**Re-baselined 2026-08-20** against `dev` at `39a5dcdb` (95 commits landed while this
audit was in review). Every probe was re-run at the new HEAD. Material changes:
**F-1 is fixed** (#2216 makes unknown reference-CSV columns a hard error, with a
regression test on the #1545 fixture), and the #2091 / #2050 / #1186 series removed
several of the silent-degradation paths F-11 pointed at. F-2 (residual), F-3 (mostly),
F-4, F-5, F-6, F-7 were re-verified **still open** at `39a5dcdb`.

**Re-baselined 2026-08-25** against `dev` at `bf6d808a`. Sections A–C now state the
current behavior: rows fixed since the first snapshot show today's state with the PR
that fixed them, and the pre-fix evidence stays in the finding text of section C. The
only change to audited surface since the 2026-08-24 sweep is #2307
(research-facilities `use` bounds, D-8).

### Full-spec systematic sweep (2026-08-24)

After #2231/#2291 shipped, the whole spec was swept mechanically once (throwaway
scripts, per the decision to keep the backend as SSOT with no permanent doc
parser): all 45 tables of `data-description.md` parsed into structured rules
(~280 fields), all 13 entry Create DTOs probed against every parsed constraint
(~150 accept/reject probes off valid base payloads), all 14 FactorCreate DTOs
and all 8 frontend module configs diffed against the same spec. The doc repo
itself moved (Aug 17–19): travel `user_institutional_id` is now documented
optional (closes most of D-7) and process emissions `quantity` was renamed
`quantity_kg` — but **D-1 is still stale** (the doc still lists the
`"1-5 times per day"` labels the backend rejects).

Sweep verdict: the code implements the documented scheme **except**:

| #    | Finding                                                                                                                                                                                                                         | Class                  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| N-1  | `purchase_institutional_code` (required string) accepts whitespace-only — the F-10 sweep in #2231 missed this one field.                                                                                                        | code-gap (small fix)   |
| N-2  | "numbers only" is never enforced: headcount and train `user_institutional_id` accept `"abc"`.                                                                                                                                   | decision (code or doc) |
| N-3  | Equipment form requires `sub_class` and both usage-hour fields; the DTO has all three optional (CSV may omit them).                                                                                                             | FE-stricter — confirm  |
| N-4  | Process-emissions `subcategory`: doc says required for Refrigerants only, DTO never requires it, form always requires it. Three-way disagreement (= D-5).                                                                       | decision               |
| N-5  | Headcount member `fte`: backend caps at 1, form has `min: 0` but no `max` — a 1.5 in the form 422s only after submit. Entangled with D-4 (students uncapped).                                                                   | FE gap after D-4 call  |
| N-6  | `purchases_common_factors.csv`: doc + the committed CSV carry `purchase_institutional_description`; the DTO has `translation_key` instead — verify mapping.                                                                     | to-verify              |
| N-7  | Train DTO accepts undocumented `origin_natural_key` / `destination_natural_key`.                                                                                                                                                | doc addition (D list)  |
| N-8  | Building grey energy has a Create DTO (`BuildingEmbodiedEnergyHandlerCreate`) but no `*_data.csv` table in the doc (factors only).                                                                                              | doc gap or WIP module  |
| N-9  | Travel `number_of_trips`: doc mandatory, DTO optional with default 1 (form requires it).                                                                                                                                        | trivial                |
| N-10 | Doc note (L47): headcount `fte` "can be completed directly in the table if not provided in the file" — but the DTO requires it non-null, so an fte-less CSV row is rejected, never landing in the table to complete.            | decision (code or doc) |
| N-11 | Doc note (L28): "rows that don't meet mandatory requirements will be ignored during upload" — no longer true: reference/factor CSVs fail hard since #2216/#2231, and entry rows are skipped with a reported error, not ignored. | doc-stale              |

The doc's admonition notes and prose were swept separately (all 13 blocks read,
2026-08-24): the General Notes confirm the `kg_co2eq` out-of-band override and the
ISO-date rule (both enforced), state an upload-order rule that is deliberately
unenforced, and produced findings N-10 and N-11 above; the headcount template
note self-declares a stale table for the D list.

Non-findings the sweep cleared: `kg_co2eq` in every data CSV is honored
out-of-band by the entry pipeline (deliberately never in `DataEntry.data`);
`unit_institutional_id` is the routing column, correctly absent from DTOs;
factor `*_category` columns are routing columns consumed outside the DTOs with
code comments saying so; all other factor tables match their FactorCreate DTOs
field-for-field. Confirmed still open: D-1, D-5, D-6, F-5 (every DTO still
accepts an unknown key — S3/S5), and the F-9/F-13 product questions.

## A. Path-level behavior matrix

The headline result: most holes are **per-path mechanics**, shared by every module
that flows through the path — not per-field rules.

| Behavior                                                       | P1a reference CSVs (`csv_providers/reference_data.py`)                                                                                                                                   | P1b factor CSVs (`base_factor_csv_provider.py`)                                                                                                                                          | P2 entry CSVs (`base_csv_provider.py`)                                                                                                        | P3 form input (`schemas/data_entry.py` + module DTOs)                                                                                                                                                           | P4 reduction-objective CSVs (`schemas/year_configuration.py:191-265`) |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Unknown column / key                                           | ✅ hard error since #2216 (was warn-only → **F-1**, fixed)                                                                                                                               | ⚠️ no check at all                                                                                                                                                                       | ⚠️ silently dropped by `filtered_row` (`:1234-1239`); columns named `data` or `status` **survive** the filter (they are DTO fields) → **F-4** | ⚠️ swept into persisted `data` — verified on **all 15** Create DTOs → **F-5**                                                                                                                                   | ⚠️ no unknown-column check (`missing = expected - actual` only)       |
| Missing required column                                        | ✅ fails, but checked against the **first row only** (`:235-252`)                                                                                                                        | ✅ per-row DTO `ValidationError`                                                                                                                                                         | ✅ fails only if **all of the first 5 rows** lack it (`:346-356`)                                                                             | ✅ pydantic required fields                                                                                                                                                                                     | ✅ full header check, every row validated, all errors collected       |
| Strictness switch                                              | n/a                                                                                                                                                                                      | `strict_column_validation` read (`:302`) but **set nowhere** in `app/`                                                                                                                   | same flag read (`:327`), **set nowhere** → **F-4**                                                                                            | n/a                                                                                                                                                                                                             | n/a                                                                   |
| Type-coercion failure                                          | ✅ since #2231: a present unparseable value raises (`_to_float`, `:542-556`); absent/blank/`-` → `None` (was silent NULL → **F-2**, fixed)                                               | ✅ since #2231: validated DTO fields are copied back before persistence (`:417-420`); an unparseable numeric fails the row (was discarded DTO + raw-string passthrough → **F-3**, fixed) | ✅ per-row DTO error, recorded in `row_errors`                                                                                                | ✅ rejected (`float_parsing`); numeric strings coerced (`'1.5' → 1.5`) — but coercion _failures_ fall through to pydantic silently at debug level (`data_entry.py:63-66`)                                       | ✅ per-row pydantic model, ranges enforced                            |
| Client-supplied `data` key                                     | n/a                                                                                                                                                                                      | n/a                                                                                                                                                                                      | possible (column named `data` survives) — unprobed end-to-end                                                                                 | ⚠️ **bypasses all field validation**: declared fields validate then are discarded; the arbitrary dict is persisted → **F-6**                                                                                    | n/a                                                                   |
| Referential integrity (category/class/code must match factors) | n/a                                                                                                                                                                                      | ✅ `get_factor_emission_type_id` fails the row                                                                                                                                           | fail-fast when factors absent (`_guard_factors_required`, `:154-186`)                                                                         | not at DTO level                                                                                                                                                                                                | n/a                                                                   |
| …and at compute time                                           | —                                                                                                                                                                                        | —                                                                                                                                                                                        | —                                                                                                                                             | ⚠️ a factor/unit mismatch yields **silently empty computations** — pinned by `test_resolve_computations_without_factor_id_returns_empty`, `test_unit_mismatch_between_entry_and_factor_returns_none` → **F-11** | —                                                                     |
| Failure surface                                                | ✅ since #2216: hard `ValueError` before any delete (was job SUCCESS with every surface NULL → **F-1**, fixed)                                                                           | job `row_errors` in meta (capped at 100)                                                                                                                                                 | job `row_errors` / SSE                                                                                                                        | four different error envelopes (`detail:str`, `{code,fields}`, `{errors:[...]}`, FastAPI list) → **F-12** (recorded, deferred)                                                                                  | `422 {"detail":{"errors":[...]}}` — all rows, all errors              |
| Destructive semantics                                          | ⚠️ building-rooms ingest is **delete-then-reinsert** (`:495-538`) — one bad upload wipes the table; since #2216 the header check runs first, so a typo'd column can no longer trigger it | per-type delete before ingest                                                                                                                                                            | re-upload semantics (tested)                                                                                                                  | n/a                                                                                                                                                                                                             | n/a                                                                   |

**P4 is the in-repo reference pattern**: synchronous, every row validated against a
pydantic row model, all errors collected and returned together
(`validate_reduction_objective_csv`), before anything persists. The fixes below copy
it, they don't invent anything new.

### The #1545 chain, reproduced (pre-#2216)

```
fixture header: building_location,building_name,room_name,room_type,room_surface_square_meters
_validate_headers(...)   → PASSES; logs only
  "WARNING Reference CSV has unexpected columns (ignored): room_surface_square_meters"
required set = {building_location, building_name, room_name}       ← surface not in it
_to_float(raw.get("room_surface_square_meter")) = _to_float(None) → None
delete(BuildingRoom); re-insert all rows with surface=NULL; flush  → job SUCCESS
```

Since #2216 the first step raises on the unexpected column and nothing below it
runs (regression test on this fixture).

## B. Per-module field rules

Verdicts: `OK` (doc = backend, frontend consistent) · `GAP-BE` / `GAP-FE` (rule
missing on that side) · `DIV` (both enforce, rules differ) · `DOC-STALE` (deliberate
code behavior, doc behind) · `?` (needs a decision). Backend refs are the Create DTOs
in `backend/app/modules/<m>/data_entries.py`; frontend refs are
`frontend/src/constant/module-config/<m>.ts` plus the shared validator
`ModuleForm.vue:931-1059`. Every module additionally inherits **F-5/F-6** (unknown-key
sweep, `data`-key bypass) on P3 and the P1/P2 mechanics above — not repeated per row.

### Headcount (`headcount/data_entries.py`, `headcount.ts`)

| Field                 | Doc                    | Backend                                                             | Frontend                                     | Verdict                                                 |
| --------------------- | ---------------------- | ------------------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------- |
| name                  | required, non-empty    | required, non-empty, stripped (`:32-39`; test pins strip)           | required ✅ (`headcount.ts:27`, since #2231) | OK                                                      |
| sius_code             | required, values 51–59 | required, enum `{51,52,53,54,56,57,58,59}` (`:9`) — **55 excluded** | select, required ✅ (since #2231)            | **DOC-STALE** on 55 (D-3)                               |
| user_institutional_id | required, numbers only | required, non-empty (`:41-47`) — no numbers-only check              | required ✅                                  | **DIV** minor: digits-only unenforced BE+FE (F-9 / N-2) |
| fte (member)          | required, 0 ≤ v ≤ 1    | required, 0–1 (`:49-58`)                                            | required, min 0 / max 1 ✅ (since #2231)     | OK                                                      |
| fte (student)         | (same table) 0 ≤ v ≤ 1 | required, **≥ 0 only — no upper bound** (`:72-77`)                  | required, min 0, no max (since #2231)        | **?** upper bound (D-4)                                 |

### Process emissions (`process_emissions/data_entries.py`, `process_emissions.ts`)

| Field       | Doc                                     | Backend                                                                                    | Frontend                                                                               | Verdict                                  |
| ----------- | --------------------------------------- | ------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------- | ---------------------------------------- |
| category    | required, must match factors            | required, non-empty after strip (`:24-29`, since #2231); match at factor resolution (F-11) | select, required ✅                                                                    | OK                                       |
| subcategory | optional; **required for Refrigerants** | optional — conditional rule **nowhere** at DTO level                                       | select, **required: true** (`process_emissions.ts:29`)                                 | **?** three-way disagreement (N-4 / D-5) |
| quantity_kg | required, ≥ 0                           | required, ≥ 0 (`:31-36`; tested)                                                           | required, **min 0.001** (`process_emissions.ts:51`) — forbids the 0 the backend allows | **DIV** (F-9)                            |

### Buildings — rooms (`buildings/data_entries.py:74-95`, `buildings.ts`)

| Field                                    | Doc                        | Backend                                                                                 | Frontend                                                     | Verdict                             |
| ---------------------------------------- | -------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------- |
| building_name                            | required, within reference | required (reference match at compute)                                                   | select from reference, required ✅                           | OK                                  |
| room_name                                | required                   | required                                                                                | select, required ✅                                          | OK                                  |
| room_type                                | required, 6-value enum     | **required**, enum matches doc (`:48-56, :81-87`)                                       | select, required ✅ (`buildings.ts:42`, since #2231)         | OK                                  |
| room_allocation_ratio                    | optional, 0 ≤ v ≤ 1        | optional, 0–1 (`:89-93`)                                                                | number, min 0 / max 1 ✅ (`buildings.ts:83-84`, since #2231) | OK                                  |
| room_surface_square_meter                | (reference file, not data) | `DiscardClientSurfaceMixin` silently pops a client value (`:59-72`) — server-side truth | shown as a form field                                        | consistency note (F-9)              |
| heating/cooling/ventilation/lighting kwh | not in doc data file       | **not Create-DTO fields** → if sent, they ride the F-5 sweep into `data`                | present in config                                            | **F-5 dependent** — inventory in S5 |

### Buildings — energy & combustions (`buildings/data_entries.py:129-139`, `buildings.ts:167-226`)

| Field    | Doc                          | Backend                                                                                                        | Frontend                                     | Verdict                                                       |
| -------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------- |
| name     | required, must match factors | required                                                                                                       | select, required ✅                          | OK                                                            |
| unit     | **required**, SI format      | **no `unit` field on the Create DTO at all** (only on `EnergyCombustionBase`) — a CSV `unit` column is dropped | text, not required                           | **?** (D-6) — doc requires a column the backend cannot accept |
| quantity | required, ≥ 0                | required, ≥ 0 (`:134-139`)                                                                                     | required, **min 0.001** (`buildings.ts:212`) | **DIV** (F-9)                                                 |

### Equipment (`equipment/data_entries.py`, `equipment.ts`)

| Field                               | Doc                                       | Backend                                           | Frontend                                                                                                                                                                                                | Verdict                              |
| ----------------------------------- | ----------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| equipment_id                        | required, alphanumeric                    | required, non-empty after strip (`:83-88`)        | required ✅                                                                                                                                                                                             | OK                                   |
| name / equipment_class              | required                                  | required, non-empty after strip                   | required ✅                                                                                                                                                                                             | OK                                   |
| sub_class                           | optional, class/subclass tuple in factors | optional                                          | **required: true** + stray `min: 0` on a select (`equipment.ts:75-76`)                                                                                                                                  | **DIV** — FE stricter, confirm (N-3) |
| active/standby_usage_hours_per_week | optional int, 0–168, sum ≤ 168            | optional, 0–168 each **and** sum ≤ 168 (`:14-55`) | **required: true**, min 0 / max 168, sum rule in `ModuleForm.vue:783`; the shared validator gained an `integer` bound in #2307 (`:1135`) but this config does not set it (1.5 still passes FE, 400s BE) | **DIV** (N-3, F-9)                   |
| active/standby_power_w              | not in doc data file                      | **not Create-DTO fields** → F-5 sweep if sent     | required number fields in config                                                                                                                                                                        | **F-5 dependent** — inventory in S5  |

### External cloud & AI (`external_cloud_and_ai/data_entries.py`, `external-cloud-and-ai.ts`)

| Field                          | Doc                                | Backend                                                                                                                                               | Frontend                 | Verdict                                                   |
| ------------------------------ | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ | --------------------------------------------------------- |
| service_type (cloud)           | storage \| compute                 | plain `str` — **no enum**; match happens at factor resolution (silent on miss, F-11)                                                                  | select, required ✅      | **GAP-BE** (F-10)                                         |
| provider                       | within factors                     | plain `str`, same                                                                                                                                     | select, required ✅      | OK-ish (F-11)                                             |
| spent_amount                   | required, ≥ 0                      | required, ≥ 0 (`:64-69`)                                                                                                                              | required, min 0 ✅       | OK                                                        |
| currency (cloud)               | optional; chf/eur/usd, default eur | matches exactly (`:71-80`), whitespace/empty → eur                                                                                                    | optional select          | **OK**                                                    |
| requests_per_user_per_day (AI) | "1-5 times per day", …             | tokens `1_5, 5_20, 20_100, gt_100` (`:11-16`); **labels deliberately rejected** (pinned by `test_external_ai_create_rejects_legacy_frequency_labels`) | select with token values | **DOC-STALE** (D-1) — a CSV following the doc is rejected |
| fte_count                      | required, ≥ 1                      | required, **≥ 0.1** (`:102-107`)                                                                                                                      | required, min 0.1        | **DOC-STALE** (D-2): doc says ≥ 1, code deliberately 0.1  |

### Professional travel (`professional_travel/data_entries.py`, `professional-travel.ts`)

| Field                                    | Doc                                              | Backend                                                                                                                                                 | Frontend                                                     | Verdict                                                                                                                   |
| ---------------------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| origin/destination (iata / name+country) | required                                         | required                                                                                                                                                | direction-input, required ✅                                 | OK                                                                                                                        |
| user_institutional_id                    | **optional**, numbers only                       | `str \| None` **without default → key required, value nullable**; deliberate (pinned by `test_plane_create_still_requires_the_field`, sentinel SCIPERs) | headcount-member-select, not required (always sends the key) | **DOC-STALE** (D-7)                                                                                                       |
| departure_date                           | optional, ISO                                    | optional, multi-format parse (`:37-57`)                                                                                                                 | date, optional, year-bounded                                 | OK                                                                                                                        |
| number_of_trips                          | required int, ≥ 1                                | default 1, ≥ 1 (`:102-106,:132-136`)                                                                                                                    | required, min 1 (`professional-travel.ts:81-82`)             | **OK** — an earlier exploration claim that the form skips this was wrong; the config `min: 1` feeds the generic min check |
| cabin_class                              | plane first/business/economy; train first/second | enum mixins (`:13-34`)                                                                                                                                  | select, required ✅                                          | OK                                                                                                                        |

### Purchases (`purchase/data_entries.py`, `purchase.ts`)

| Field                                     | Doc                                        | Backend                                                                                                                                                                                | Frontend                                                | Verdict             |
| ----------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------- |
| name                                      | required, non-empty                        | required, non-empty after strip (`:36-42`, since #2231)                                                                                                                                | required ✅                                             | OK                  |
| supplier / quantity                       | optional; quantity ≥ 0                     | optional; ≥ 0 (`:57-64`)                                                                                                                                                               | optional; min 0 ✅                                      | OK                  |
| total_spent_amount                        | required, ≥ 0                              | required, ≥ 0                                                                                                                                                                          | required, min 0 ✅                                      | OK                  |
| currency                                  | optional; chf/eur/usd/gbp/aud, default chf | optional, default chf, **9-value list** aud/cad/chf/cny/eur/gbp/jpy/sek/usd (`:84-100`); the code even carries the comment _"doc say mandatory, but with default -> optional"_ (`:37`) | optional select                                         | **DOC-STALE** (D-2) |
| purchase_institutional_code               | required, UNSPSC, match factors            | required, **length ≥ 1 only** (`:82-89`) — whitespace-only accepted                                                                                                                    | select, required ✅                                     | **GAP-BE** (N-1)    |
| centralized: name/unit/annual_consumption | required                                   | required                                                                                                                                                                               | required ✅                                             | OK                  |
| centralized: coef_to_kg                   | required                                   | required, ≥ 0 (`:111-115`)                                                                                                                                                             | required, min 0 ✅ (`purchase.ts:140-141`, since #2231) | OK                  |

### Research facilities (`research_facilities/data_entries.py`, `research-facilities.ts`)

| Field                                              | Doc                      | Backend                                                                                                                                | Frontend                                                                                         | Verdict                                              |
| -------------------------------------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| researchfacility_id / name                         | required, within factors | required, non-empty (common: `:36-48`)                                                                                                 | name select required; id derived                                                                 | OK                                                   |
| use (common)                                       | required, ≥ 0            | required, numeric, ≥ 0 (`:104-113`); bounded per `use_unit` since #2307 (`:46-64`: `%` ≤ 100, `hours` ≤ 8736, `housings` integer-only) | number, required, min 0 + the same per-unit bounds (`research-facilities.ts:43-58`, since #2307) | OK — code stricter than doc (D-8)                    |
| use_unit                                           | required, within factors | required, non-empty (common `:115-123`)                                                                                                | text, required ✅ (`research-facilities.ts:69-72`, since #2307)                                  | OK                                                   |
| **animal:** researchfacility_type / use / use_unit | required; use ≥ 0        | required; `use` ≥ 0 and non-empty ids since #2231 (`:195-218`); per-unit bounds since #2307                                            | required + the same bounds (`research-facilities.ts:98-157`, since #2307)                        | OK (was **GAP-BE** F-7 + **GAP-FE** F-8, both fixed) |

### Planner modules (`modules_planner/*/data_entries.py`)

`PlannerPurchaseCreate`: category enum + `amount_eur ≥ 0`, both tested. `PlannerHeadCountCreate`: sius enum + fte rules. Verdict OK at DTO level — but planner kinds are **exempt** from the update-path field firewall (F-6/F-7 exposure, `data_entry_permissions.py:79-80`).

### Reduction objectives (P4)

Row models enforce ranges (`co2 ≥ 0`, `pop ≥ 0`, `0 ≤ reduction_percentage ≤ 1`),
tested in `tests/unit/schemas/test_year_configuration.py:99-146`. Verdict **OK** —
the pattern to copy. (Unknown columns still unchecked, folded into F-4's fix family.)

## C. Findings

Classification: `code-gap` (fix in a slice below) · `doc-stale` (section D) ·
`test-gap` (regression test ships with the owning slice).

- **F-1 · ~~code-gap~~ FIXED by #2216 (2026-08-20)** — Reference-CSV header
  validation could not fail on a typo'd optional column: unknown columns were
  warn-only, and building-rooms ingest is delete-then-reinsert — so #1545's typo
  wiped every `room_surface_square_meter` while the job reported SUCCESS
  (reproduced with the committed fixture). #2216 turns unknown columns into a hard
  `ValueError` before anything is deleted, with a regression test on that fixture.
  Re-verified: the fixture is now rejected.
- **F-2 · ~~code-gap~~ FIXED by #2231 (S2)** — After #2216, `_to_float`
  (`reference_data.py`) still mapped a _present but unparseable_ value to `None`
  silently — `_to_float('12,5') → None` (re-probed at `39a5dcdb`), so a wrong decimal
  separator NULLed data with no row error. #2231 makes it raise; absent, blank and
  `-` cells stay legal `None`s (`:542-556`).
- **F-3 · ~~code-gap (partial)~~ FIXED by #2231 (S2)** — Factor providers validated
  rows but persisted the **unvalidated** hand-built dicts (`validate_create`'s return
  value discarded, `_convert_value` keeping raw strings when `float()` failed), so DTO
  coercions never reached the DB. Since #2231 the validated DTO fields are copied
  back into `values` before persistence (`base_factor_csv_provider.py:417-420`;
  `classification` stays hand-built on purpose — the 310B identity index keys on
  it) and an unparseable numeric fails the row; #2291 pins that accepted rows persist
  their DTO-normalized form. _(#2091 had earlier made an unmappable emission type
  abort the whole upload.)_
- **F-4 · code-gap · S3** — Entry-CSV header check samples 5 rows and fails only if
  _all_ lack the required columns; `strict_column_validation` is read in both base
  providers but set nowhere; unknown columns are silently dropped by `filtered_row`
  (`base_csv_provider.py:1234-1239`); and CSV columns literally named `data` or
  `status` survive the filter because both are DTO fields (probe: both in
  `model_fields`).
- **F-5 · code-gap · S5** — `DataEntryPayloadMixin.unflatten_payload`
  (`data_entry.py:37-48`) sweeps every unknown/typo'd key into the persisted `data`
  dict. Probe: **all 15** module Create DTOs accept `typo_field_xyz: 42` and persist
  it. A typo on an optional field (`note` → `notes`) silently loses the value.
- **F-6 · code-gap · S5** — A client-supplied `data` key **bypasses field validation
  entirely**: with valid declared fields alongside, validation passes on those, then
  the arbitrary `data` dict is what persists (probe:
  `data == {'totally': 'arbitrary'}`). The create route takes `item_data: dict`
  (`carbon_report_module.py:844`), so any authenticated user can write arbitrary JSON
  into `data_entries.data`.
- **F-7 · code-gap · S4/S5** — Enforcement is asymmetric: update has an accidental
  extra-key firewall via `FIELD_NOT_EDITABLE` (`data_entry_permissions.py`), create
  has none; planner kinds and `building_embodied_energy` are exempt even on update;
  `status` is a settable DTO field on exempt paths. The DTO part
  (`ResearchFacilitiesAnimalHandlerCreate` accepted `use = -5` and empty ids) was
  fixed in #2231 (S4); only the permission asymmetry remains (S5).
- **F-8 · ~~code-gap (FE)~~ FIXED by #2231 (S6) + #2307** — Frontend config missed
  backend rules: headcount `name`/`sius_code`/`fte` not required; buildings
  `room_type` not required and `room_allocation_ratio` unbounded; centralized-purchase
  `coef_to_kg` optional/unbounded (all fixed in #2231); RF `use` an optional _text_
  field and `use_unit` not required (fixed in #2307, which also added per-unit bounds
  on both sides). The converse — `sub_class`, usage-hours and `power_w` _stricter or
  absent-in-DTO_ on the frontend — is not a frontend gap: it is N-3 (confirm) and the
  S5 inventory.
- **F-9 · code-gap (both) · S4+S6, partly open** — Cross-cutting rule drift: FE
  `min: 0.001` where BE/doc allow 0 (`quantity_kg`, buildings `quantity`) — product
  answer pending; no integer check FE-side for `int` fields (1.5 passes FE, 400s BE —
  the shared validator gained an `integer` bound in #2307, the equipment config just
  doesn't set it); `user_institutional_id` digits-only unenforced anywhere (N-2).
  _The "FE never trims before its required check" clause is fixed by #2231
  (`ModuleForm.vue:1112`)._
- **F-10 · ~~code-gap~~ FIXED by #2231 (S4), one residual** — Whitespace-only
  required strings were rejected by equipment, headcount and common-RF only;
  process_emissions (probe: `category: '   '` accepted), purchase and others let them
  through. #2231 added the `_non_empty` check to every required string field —
  except `purchase_institutional_code`, whose validator still checks length only
  (N-1, small fix pending). The 24 copy-pasted `_non_empty` validators are
  themselves the subject of the lead's normalization plan on #1489 (2026-08-24).
- **F-11 · observation (pipeline) · being addressed by the lead** — Referential
  mismatches (category/class/code vs factors) resolved at compute time to
  **silently empty computations** — the mechanism that turned #1545's NULLs into
  "results not calculated" with no error. _Update 2026-08-20:_ the lead is actively
  closing these: #2091 ("resolve an emission type or fail hard, never degrade",
  SF6/NF3 leaves), #2050 ("fail hard instead of publishing a wrong-but-plausible
  total", six silent fallbacks removed, `_apply_formula` now raises its reason),
  and #1186 (plane unknown-IATA raises instead of silently zero-emission; train
  not-found station is a hard row error; API creates missing a resolved
  `natural_key` rejected). The compute path remains outside this audit's scope
  (pipeline internals, 310-series) — the residual question for the lead is whether
  any `returns_empty` branches are still reachable after that series.
- **F-12 · observation · deferred** — Four different validation-error envelopes reach
  the frontend plus the async job channel. Unifying them is an architecture change —
  parked pending a decision with the lead.
- **F-13 · code-gap (FE) · S6 — new since re-baseline** — #2061 (`8609717a`) gives
  the Explorer's external-AI form a prefilled `fte_count` of `0`
  (`explorerDefault: 0` in `external-cloud-and-ai.ts`), but both the frontend rule
  (`min: 0.1`) and the backend validator (`fte_count >= 0.1`) reject 0 — so the
  Explorer now pre-fills a value that cannot be submitted unchanged. Confirm
  whether that friction is intended before S6 touches the field.
- **Constraint (S5)** — `percentage_of_reference_year` deliberately rides the F-5
  sweep into `data` (`data_entry_permissions.py:65-68`). Any F-5/F-6 fix must keep it
  working — the clean route is promoting it to an explicit field.

## D. Doc-stale report — for the data manager

Deliberate backend behavior the doc doesn't reflect. Each row cites why we read it as
deliberate. **No code slice fixes these**; the doc (or a data-manager decision) does.

| #   | Where                                       | Doc says                  | Code does                                                                                                                                     | Why we call it deliberate                                                                                                                   |
| --- | ------------------------------------------- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| D-1 | external AI `requests_per_user_per_day`     | `"1-5 times per day"`, …  | stores tokens `1_5 / 5_20 / 20_100 / gt_100`; labels **rejected**                                                                             | pinned by `test_external_ai_create_rejects_legacy_frequency_labels`. ⚠️ A CSV written from the doc is rejected today.                       |
| D-2 | purchase `currency`; AI `fte_count`         | 5 currencies; fte ≥ 1     | 9 currencies (adds cad/cny/jpy/sek); fte ≥ 0.1                                                                                                | explicit lists/validators, comment at `purchase/data_entries.py:37`                                                                         |
| D-3 | headcount `sius_code`                       | 51–59                     | 55 excluded from the enum                                                                                                                     | explicit set `{51,52,53,54,56,57,58,59}`                                                                                                    |
| D-4 | headcount student `fte`                     | 0 ≤ v ≤ 1 (member table)  | ≥ 0 only, no upper bound                                                                                                                      | separate validator without the cap — confirm intent                                                                                         |
| D-5 | process-emissions `subcategory`             | required for Refrigerants | no conditional rule anywhere; a Refrigerants row without subcategory just resolves no factor (silently, F-11)                                 | needs a decision: DTO-enforce or document as-is                                                                                             |
| D-6 | energy-combustions `unit`                   | required column           | the Create DTO has **no `unit` field**; a CSV `unit` column is dropped                                                                        | unit comes from the factor; doc column cannot be honored — confirm and update doc                                                           |
| D-7 | travel `user_institutional_id`              | optional                  | key required, value nullable (sentinel SCIPERs)                                                                                               | pinned by `test_plane_create_still_requires_the_field`                                                                                      |
| D-8 | research-facilities `use` (common + animal) | required, ≥ 0             | bounded per `use_unit` since #2307: `%` ≤ 100, `hours` ≤ 8736 (= `HOURS_PER_WEEK × WEEKS_PER_YEAR`), `housings` integer-only, `CHF` unbounded | explicit `use_bounds()` table (`research_facilities/data_entries.py:26-44`) whose comment says the factor carries no bounds — document them |

## E. Follow-up slices

Ordered; each is one small PR to `dev` with its own regression test. S1–S2 are
independent and can go in parallel. This audit is **S0** (docs only).

| Slice      | Scope                                                                                                                                                                                                                                                                                                                                           | Owner findings            | Gate                                                                                                                |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| ~~**S1**~~ | **Shipped as #2216 (2026-08-20, by the lead)** while this audit was in review: unknown reference-CSV columns are a hard error before the delete-then-reinsert, regression-tested on the wrong-column fixture. The `_to_float` residual (F-2) moves to S2.                                                                                       | F-1 ✅                    | done                                                                                                                |
| **S2**     | Factor providers persist `validate_create`'s validated output; unparseable numerics = row error, not raw-string passthrough — in both `_convert_value` (factors) and `_to_float` (reference data, the F-2 residual).                                                                                                                            | F-2, F-3                  | ✅ merged in #2231 (v1.4.0)                                                                                         |
| **S3**     | Entry-CSV strict columns: reject unknown columns (incl. `data`/`status`), validate the full header not a 5-row sample — smallest diff wins (likely: enable + harden `strict_column_validation`); surface through the existing `row_errors` channel.                                                                                             | F-4                       | **lead heads-up** — flips a default for all entry ingestion                                                         |
| **S4**     | Backend DTO consistency fixes: animal-RF validators (use ≥ 0, non-empty ids), whitespace-strip on required strings everywhere, digits-only `user_institutional_id` (if confirmed).                                                                                                                                                              | F-7 (DTO part), F-9, F-10 | ✅ merged in #2231 (v1.4.0) — residual N-1 (`purchase_institutional_code`)                                          |
| **S5**     | `unflatten_payload` hardening: reject unknown keys on create, close the `data`-key bypass, promote `percentage_of_reference_year` to an explicit field, revisit `status` settability and the planner/embodied-energy exemptions. First inventory every FE-sent key not in a Create DTO (`power_w`, kwh fields, `room_surface_square_meter`, …). | F-5, F-6, F-7             | **lead sign-off** — permission scoping                                                                              |
| **S6**     | Frontend config parity: required flags, min/max bounds, drop the 0.001 minimums (or confirm them), integer check for `int` fields, trim before required. Mechanical edits to `module-config/*.ts` + the shared validator only.                                                                                                                  | F-8, F-9, F-13            | ✅ merged in #2231 (v1.4.0), RF part in #2307 — F-9 0.001-min, int check and F-13 still open, need a product answer |
| **S7**     | Frontend↔backend contract test, phase (a): a backend script exports effective DTO constraints (required/type/enum/range) to a committed JSON fixture + a freshness test; a frontend Playwright unit spec (existing `tests/unit` pure-function pattern) walks `MODULES_CONFIG` against it. No CI plumbing.                                       | pins S6 permanently       | **async ack** — adjacent to ADR-020, but derived _from_ the backend so SSoT holds                                   |
| **S8**     | Real-backend Playwright e2e validation suite (needs CI postgres+backend, `/api` proxy for the preview server, `login-test`). Anchor: the `test.fixme` at `frontend/tests/integration/backoffice-config.spec.ts:408`.                                                                                                                            | —                         | **parked with the lead**, like F-11, F-12 and the doc-automation bonus                                              |

## Verification of this slice

```bash
make build-docs                                   # docs build with this file
uv run --directory backend pytest tests/unit/modules/ tests/unit/services/data_ingestion/ -q
                                                  # targeted subset (433 passed at baseline); `make test` = full suite
git diff --stat origin/dev...HEAD -- ':!docs'     # empty — docs-only PR
```
