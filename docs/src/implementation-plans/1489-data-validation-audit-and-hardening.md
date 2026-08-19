---
issue: 1489
status: in-progress
last_updated: 2026-08-19
title: "Data-validation audit and hardening — backend as single source of truth"
summary:
  "Slice 1 of #1489: a systematic audit of every documented data rule (back-office
  doc site, data-description pages) against actual backend enforcement, frontend
  enforcement, and test coverage, across the three ingestion paths (back-office
  reference/factor CSVs, entry CSVs, direct form input). Every claim was re-verified by
  probing the DTOs and replaying fixtures. Mismatches are classified code-gap or
  doc-stale (the latter handed to the data manager, not fixed in code), and the audit
  ends in an ordered set of small follow-up PRs, starting with the #1545 reference-CSV
  silent-wipe hole. The cross-repo doc-change automation bonus is parked."
---

# Data-validation audit (#1489)

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

## A. Path-level behavior matrix

The headline result: most holes are **per-path mechanics**, shared by every module
that flows through the path — not per-field rules.

| Behavior                                                       | P1a reference CSVs (`csv_providers/reference_data.py`)                                             | P1b factor CSVs (`base_factor_csv_provider.py`)                                                                                                                            | P2 entry CSVs (`base_csv_provider.py`)                                                                                                        | P3 form input (`schemas/data_entry.py` + module DTOs)                                                                                                                                                           | P4 reduction-objective CSVs (`schemas/year_configuration.py:191-265`) |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Unknown column / key                                           | ⚠️ warn-only, never fails the job (`:253-258`) → **F-1**                                           | ⚠️ no check at all                                                                                                                                                         | ⚠️ silently dropped by `filtered_row` (`:1234-1239`); columns named `data` or `status` **survive** the filter (they are DTO fields) → **F-4** | ⚠️ swept into persisted `data` — verified on **all 15** Create DTOs → **F-5**                                                                                                                                   | ⚠️ no unknown-column check (`missing = expected - actual` only)       |
| Missing required column                                        | ✅ fails, but checked against the **first row only** (`:235-252`)                                  | ✅ per-row DTO `ValidationError`                                                                                                                                           | ✅ fails only if **all of the first 5 rows** lack it (`:346-356`)                                                                             | ✅ pydantic required fields                                                                                                                                                                                     | ✅ full header check, every row validated, all errors collected       |
| Strictness switch                                              | n/a                                                                                                | `strict_column_validation` read (`:302`) but **set nowhere** in `app/`                                                                                                     | same flag read (`:327`), **set nowhere** → **F-4**                                                                                            | n/a                                                                                                                                                                                                             | n/a                                                                   |
| Type-coercion failure                                          | ⚠️ `_to_float('abc') → None`, `_to_float(None) → None` — silent NULL (`:541-550`) → **F-2**        | ⚠️ `_convert_value` keeps the raw **string** for optional numerics (`:649-658`); DTO-validated output is **discarded** — hand-built dicts persisted (`:392-421`) → **F-3** | ✅ per-row DTO error, recorded in `row_errors`                                                                                                | ✅ rejected (`float_parsing`); numeric strings coerced (`'1.5' → 1.5`) — but coercion _failures_ fall through to pydantic silently at debug level (`data_entry.py:63-66`)                                       | ✅ per-row pydantic model, ranges enforced                            |
| Client-supplied `data` key                                     | n/a                                                                                                | n/a                                                                                                                                                                        | possible (column named `data` survives) — unprobed end-to-end                                                                                 | ⚠️ **bypasses all field validation**: declared fields validate then are discarded; the arbitrary dict is persisted → **F-6**                                                                                    | n/a                                                                   |
| Referential integrity (category/class/code must match factors) | n/a                                                                                                | ✅ `get_factor_emission_type_id` fails the row                                                                                                                             | fail-fast when factors absent (`_guard_factors_required`, `:154-186`)                                                                         | not at DTO level                                                                                                                                                                                                | n/a                                                                   |
| …and at compute time                                           | —                                                                                                  | —                                                                                                                                                                          | —                                                                                                                                             | ⚠️ a factor/unit mismatch yields **silently empty computations** — pinned by `test_resolve_computations_without_factor_id_returns_empty`, `test_unit_mismatch_between_entry_and_factor_returns_none` → **F-11** | —                                                                     |
| Failure surface                                                | job SUCCESS with full `rows_inserted` even when every surface is NULL → **F-1**                    | job `row_errors` in meta (capped at 100)                                                                                                                                   | job `row_errors` / SSE                                                                                                                        | four different error envelopes (`detail:str`, `{code,fields}`, `{errors:[...]}`, FastAPI list) → **F-12** (recorded, deferred)                                                                                  | `422 {"detail":{"errors":[...]}}` — all rows, all errors              |
| Destructive semantics                                          | ⚠️ building-rooms ingest is **delete-then-reinsert** (`:495-538`) — one bad upload wipes the table | per-type delete before ingest                                                                                                                                              | re-upload semantics (tested)                                                                                                                  | n/a                                                                                                                                                                                                             | n/a                                                                   |

**P4 is the in-repo reference pattern**: synchronous, every row validated against a
pydantic row model, all errors collected and returned together
(`validate_reduction_objective_csv`), before anything persists. The fixes below copy
it, they don't invent anything new.

### The #1545 chain, reproduced

```
fixture header: building_location,building_name,room_name,room_type,room_surface_square_meters
_validate_headers(...)   → PASSES; logs only
  "WARNING Reference CSV has unexpected columns (ignored): room_surface_square_meters"
required set = {building_location, building_name, room_name}       ← surface not in it
_to_float(raw.get("room_surface_square_meter")) = _to_float(None) → None
delete(BuildingRoom); re-insert all rows with surface=NULL; flush  → job SUCCESS
```

## B. Per-module field rules

Verdicts: `OK` (doc = backend, frontend consistent) · `GAP-BE` / `GAP-FE` (rule
missing on that side) · `DIV` (both enforce, rules differ) · `DOC-STALE` (deliberate
code behavior, doc behind) · `?` (needs a decision). Backend refs are the Create DTOs
in `backend/app/modules/<m>/data_entries.py`; frontend refs are
`frontend/src/constant/module-config/<m>.ts` plus the shared validator
`ModuleForm.vue:931-1059`. Every module additionally inherits **F-5/F-6** (unknown-key
sweep, `data`-key bypass) on P3 and the P1/P2 mechanics above — not repeated per row.

### Headcount (`headcount/data_entries.py`, `headcount.ts`)

| Field                 | Doc                    | Backend                                                             | Frontend                                | Verdict                                           |
| --------------------- | ---------------------- | ------------------------------------------------------------------- | --------------------------------------- | ------------------------------------------------- |
| name                  | required, non-empty    | required, non-empty, stripped (`:32-39`; test pins strip)           | **not required** (`headcount.ts:24-26`) | **GAP-FE** (F-8)                                  |
| sius_code             | required, values 51–59 | required, enum `{51,52,53,54,56,57,58,59}` (`:9`) — **55 excluded** | select, **not required**                | **GAP-FE** (F-8) + **DOC-STALE** on 55 (D-3)      |
| user_institutional_id | required, numbers only | required, non-empty (`:41-47`) — no numbers-only check              | required ✅                             | **DIV** minor: digits-only unenforced BE+FE (F-9) |
| fte (member)          | required, 0 ≤ v ≤ 1    | required, 0–1 (`:49-58`)                                            | min 0 / max 1, **not required**         | **GAP-FE** (F-8)                                  |
| fte (student)         | (same table) 0 ≤ v ≤ 1 | required, **≥ 0 only — no upper bound** (`:72-77`)                  | min 0, not required                     | **GAP-FE** + **?** upper bound (D-4)              |

### Process emissions (`process_emissions/data_entries.py`, `process_emissions.ts`)

| Field       | Doc                                     | Backend                                                                                | Frontend                                                                               | Verdict                                                                                |
| ----------- | --------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| category    | required, must match factors            | required (match at factor resolution — see F-11); **whitespace-only accepted** (probe) | select, required ✅                                                                    | **GAP-BE** whitespace (F-10)                                                           |
| subcategory | optional; **required for Refrigerants** | optional — conditional rule **nowhere** at DTO level                                   | optional select                                                                        | **?** — conditional enforced only implicitly at factor resolution, silently (F-11/D-5) |
| quantity_kg | required, ≥ 0                           | required, ≥ 0 (`:24-29`; tested)                                                       | required, **min 0.001** (`process_emissions.ts:57`) — forbids the 0 the backend allows | **DIV** (F-9)                                                                          |

### Buildings — rooms (`buildings/data_entries.py:74-95`, `buildings.ts`)

| Field                                    | Doc                        | Backend                                                                                 | Frontend                                        | Verdict                             |
| ---------------------------------------- | -------------------------- | --------------------------------------------------------------------------------------- | ----------------------------------------------- | ----------------------------------- |
| building_name                            | required, within reference | required (reference match at compute)                                                   | select from reference, required ✅              | OK                                  |
| room_name                                | required                   | required                                                                                | select, required ✅                             | OK                                  |
| room_type                                | required, 6-value enum     | **required**, enum matches doc (`:48-56, :81-87`)                                       | select, **not required** (`buildings.ts:39-41`) | **GAP-FE** (F-8)                    |
| room_allocation_ratio                    | optional, 0 ≤ v ≤ 1        | optional, 0–1 (`:89-93`)                                                                | number, **no min/max** (`buildings.ts:79-92`)   | **GAP-FE** (F-8)                    |
| room_surface_square_meter                | (reference file, not data) | `DiscardClientSurfaceMixin` silently pops a client value (`:59-72`) — server-side truth | shown as a form field                           | consistency note (F-9)              |
| heating/cooling/ventilation/lighting kwh | not in doc data file       | **not Create-DTO fields** → if sent, they ride the F-5 sweep into `data`                | present in config                               | **F-5 dependent** — inventory in S5 |

### Buildings — energy & combustions (`buildings/data_entries.py:129-139`, `buildings.ts:167-226`)

| Field    | Doc                          | Backend                                                                                                        | Frontend                | Verdict                                                       |
| -------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------- |
| name     | required, must match factors | required                                                                                                       | select, required ✅     | OK                                                            |
| unit     | **required**, SI format      | **no `unit` field on the Create DTO at all** (only on `EnergyCombustionBase`) — a CSV `unit` column is dropped | text, not required      | **?** (D-6) — doc requires a column the backend cannot accept |
| quantity | required, ≥ 0                | required, ≥ 0 (`:134-139`)                                                                                     | required, **min 0.001** | **DIV** (F-9)                                                 |

### Equipment (`equipment/data_entries.py`, `equipment.ts`)

| Field                               | Doc                                       | Backend                                           | Frontend                                                                                                                      | Verdict                             |
| ----------------------------------- | ----------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| equipment_id                        | required, alphanumeric                    | required, non-empty after strip (`:83-88`)        | required ✅                                                                                                                   | OK                                  |
| name / equipment_class              | required                                  | required, non-empty after strip                   | required ✅                                                                                                                   | OK                                  |
| sub_class                           | optional, class/subclass tuple in factors | optional                                          | **required: true** + stray `min: 0` on a select (`equipment.ts:72-73`)                                                        | **DIV** (F-8)                       |
| active/standby_usage_hours_per_week | optional int, 0–168, sum ≤ 168            | optional, 0–168 each **and** sum ≤ 168 (`:14-55`) | **required: true**, min 0 / max 168, sum rule in `ModuleForm.vue:732-752` — but no **integer** check (1.5 passes FE, 400s BE) | **DIV** (F-8, F-9)                  |
| active/standby_power_w              | not in doc data file                      | **not Create-DTO fields** → F-5 sweep if sent     | required number fields in config                                                                                              | **F-5 dependent** — inventory in S5 |

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

| Field                                     | Doc                                        | Backend                                                                                                                                                                                | Frontend                                         | Verdict              |
| ----------------------------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | -------------------- |
| name                                      | required, non-empty                        | required (no strip check)                                                                                                                                                              | required ✅                                      | OK (F-10 whitespace) |
| supplier / quantity                       | optional; quantity ≥ 0                     | optional; ≥ 0 (`:57-64`)                                                                                                                                                               | optional; min 0 ✅                               | OK                   |
| total_spent_amount                        | required, ≥ 0                              | required, ≥ 0                                                                                                                                                                          | required, min 0 ✅                               | OK                   |
| currency                                  | optional; chf/eur/usd/gbp/aud, default chf | optional, default chf, **9-value list** aud/cad/chf/cny/eur/gbp/jpy/sek/usd (`:84-100`); the code even carries the comment _"doc say mandatory, but with default -> optional"_ (`:37`) | optional select                                  | **DOC-STALE** (D-2)  |
| purchase_institutional_code               | required, UNSPSC, match factors            | required, non-empty (`:73-80`; tested)                                                                                                                                                 | select, required ✅                              | OK                   |
| centralized: name/unit/annual_consumption | required                                   | required                                                                                                                                                                               | required ✅                                      | OK                   |
| centralized: coef_to_kg                   | required                                   | required, ≥ 0 (`:111-115`)                                                                                                                                                             | **not required, no min** (`purchase.ts:137-139`) | **GAP-FE** (F-8)     |

### Research facilities (`research_facilities/data_entries.py`, `research-facilities.ts`)

| Field                                              | Doc                      | Backend                                                                                        | Frontend                                                       | Verdict                   |
| -------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------------------------- |
| researchfacility_id / name                         | required, within factors | required, non-empty (common: `:36-48`)                                                         | name select required; id derived                               | OK                        |
| use (common)                                       | required, ≥ 0            | required, numeric, ≥ 0 (`:50-58`)                                                              | **type 'text', not required** (`research-facilities.ts:24-26`) | **GAP-FE** (F-8)          |
| use_unit                                           | required, within factors | required (common)                                                                              | text, not required                                             | **GAP-FE** (F-8)          |
| **animal:** researchfacility_type / use / use_unit | required; use ≥ 0        | fields required but **zero validators** — `use = -5` **accepted** (probe), no non-empty checks | not required either                                            | **GAP-BE** (F-7) + GAP-FE |

### Planner modules (`modules_planner/*/data_entries.py`)

`PlannerPurchaseCreate`: category enum + `amount_eur ≥ 0`, both tested. `PlannerHeadCountCreate`: sius enum + fte rules. Verdict OK at DTO level — but planner kinds are **exempt** from the update-path field firewall (F-6/F-7 exposure, `data_entry_permissions.py:79-80`).

### Reduction objectives (P4)

Row models enforce ranges (`co2 ≥ 0`, `pop ≥ 0`, `0 ≤ reduction_percentage ≤ 1`),
tested in `tests/unit/schemas/test_year_configuration.py:99-146`. Verdict **OK** —
the pattern to copy. (Unknown columns still unchecked, folded into F-4's fix family.)

## C. Findings

Classification: `code-gap` (fix in a slice below) · `doc-stale` (section D) ·
`test-gap` (regression test ships with the owning slice).

- **F-1 · code-gap · S1** — Reference-CSV header validation cannot fail on a typo'd
  optional column: unknown columns are warn-only (`reference_data.py:253-258`),
  required columns are checked against the first row only, and building-rooms ingest
  is delete-then-reinsert — so #1545's typo wiped every `room_surface_square_meter`
  while the job reported SUCCESS. Reproduced with the committed fixture (section A).
- **F-2 · code-gap · S1** — `_to_float` (`reference_data.py:541-550`) maps absent
  _and unparseable_ values to `None` silently: `_to_float('abc') → None`. A wrong
  decimal separator NULLs data with no row error.
- **F-3 · code-gap · S2** — Factor providers validate rows but persist the
  **unvalidated** hand-built dicts: `handler.validate_create(...)`'s return value is
  discarded (`base_factor_csv_provider.py:392-421` — the comment says "don't rely on
  validated DTO", mirroring `seed_generic_factors.py`), and `_convert_value` keeps raw
  strings when `float()` fails. DTO coercions/normalizations never reach the DB; a
  typo'd optional numeric lands as a string in `Factor.values`.
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
  `status` is a settable DTO field on exempt paths. Also at DTO level:
  `ResearchFacilitiesAnimalHandlerCreate` has **no validators** — `use = -5` is
  accepted (probe) while the common-RF DTO rejects it.
- **F-8 · code-gap (FE) · S6** — Frontend config misses backend rules: headcount
  `name`/`sius_code`/`fte` not required; buildings `room_type` not required and
  `room_allocation_ratio` unbounded; RF `use` is an optional _text_ field;
  centralized-purchase `coef_to_kg` optional/unbounded; conversely `sub_class`,
  usage-hours and `power_w` are _stricter or absent-in-DTO_ on the frontend.
- **F-9 · code-gap (both) · S4+S6** — Cross-cutting rule drift: FE `min: 0.001` where
  BE/doc allow 0 (`quantity_kg`, buildings `quantity`); no integer check FE-side for
  `int` fields (1.5 passes FE, 400s BE); `user_institutional_id` digits-only
  unenforced anywhere; FE never trims before its required check.
- **F-10 · code-gap · S4** — Whitespace-only required strings: equipment, headcount
  and common-RF strip/reject; process_emissions (probe: `category: '   '` accepted),
  purchase and others don't. Inconsistent within one codebase.
- **F-11 · observation (pipeline) · flagged to lead** — Referential mismatches
  (category/class/code vs factors) resolve at compute time to **silently empty
  computations** — pinned by `test_resolve_computations_without_factor_id_returns_empty`
  and `test_unit_mismatch_between_entry_and_factor_returns_none`. This is the
  mechanism that turned #1545's NULLs into "results not calculated" with no error,
  and it sits in recalculation/pipeline internals (310-series) — **not audited
  further here** per guardrails; needs the lead.
- **F-12 · observation · deferred** — Four different validation-error envelopes reach
  the frontend plus the async job channel. Unifying them is an architecture change —
  parked until the lead is back.
- **Constraint (S5)** — `percentage_of_reference_year` deliberately rides the F-5
  sweep into `data` (`data_entry_permissions.py:65-68`). Any F-5/F-6 fix must keep it
  working — the clean route is promoting it to an explicit field.

## D. Doc-stale report — for the data manager

Deliberate backend behavior the doc doesn't reflect. Each row cites why we read it as
deliberate. **No code slice fixes these**; the doc (or a data-manager decision) does.

| #   | Where                                   | Doc says                  | Code does                                                                                                     | Why we call it deliberate                                                                                             |
| --- | --------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| D-1 | external AI `requests_per_user_per_day` | `"1-5 times per day"`, …  | stores tokens `1_5 / 5_20 / 20_100 / gt_100`; labels **rejected**                                             | pinned by `test_external_ai_create_rejects_legacy_frequency_labels`. ⚠️ A CSV written from the doc is rejected today. |
| D-2 | purchase `currency`; AI `fte_count`     | 5 currencies; fte ≥ 1     | 9 currencies (adds cad/cny/jpy/sek); fte ≥ 0.1                                                                | explicit lists/validators, comment at `purchase/data_entries.py:37`                                                   |
| D-3 | headcount `sius_code`                   | 51–59                     | 55 excluded from the enum                                                                                     | explicit set `{51,52,53,54,56,57,58,59}`                                                                              |
| D-4 | headcount student `fte`                 | 0 ≤ v ≤ 1 (member table)  | ≥ 0 only, no upper bound                                                                                      | separate validator without the cap — confirm intent                                                                   |
| D-5 | process-emissions `subcategory`         | required for Refrigerants | no conditional rule anywhere; a Refrigerants row without subcategory just resolves no factor (silently, F-11) | needs a decision: DTO-enforce or document as-is                                                                       |
| D-6 | energy-combustions `unit`               | required column           | the Create DTO has **no `unit` field**; a CSV `unit` column is dropped                                        | unit comes from the factor; doc column cannot be honored — confirm and update doc                                     |
| D-7 | travel `user_institutional_id`          | optional                  | key required, value nullable (sentinel SCIPERs)                                                               | pinned by `test_plane_create_still_requires_the_field`                                                                |

## E. Follow-up slices

Ordered; each is one small PR to `dev` with its own regression test. S1–S2 are
independent and can go in parallel. This audit is **S0** (docs only).

| Slice  | Scope                                                                                                                                                                                                                                                                                                                                           | Owner findings            | Gate                                                                              |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | --------------------------------------------------------------------------------- |
| **S1** | #1545: strict reference-CSV headers — fail on unknown _and_ missing columns against the full header set; `_to_float` failure on a present value = row error; a failed validation must never reach the delete-then-reinsert. Regression test = the committed wrong-column fixture.                                                               | F-1, F-2                  | none — plain bug fix                                                              |
| **S2** | Factor providers persist `validate_create`'s validated output; unparseable numerics = row error, not raw-string passthrough.                                                                                                                                                                                                                    | F-3                       | none                                                                              |
| **S3** | Entry-CSV strict columns: reject unknown columns (incl. `data`/`status`), validate the full header not a 5-row sample — smallest diff wins (likely: enable + harden `strict_column_validation`); surface through the existing `row_errors` channel.                                                                                             | F-4                       | **lead heads-up** — flips a default for all entry ingestion                       |
| **S4** | Backend DTO consistency fixes: animal-RF validators (use ≥ 0, non-empty ids), whitespace-strip on required strings everywhere, digits-only `user_institutional_id` (if confirmed).                                                                                                                                                              | F-7 (DTO part), F-9, F-10 | none                                                                              |
| **S5** | `unflatten_payload` hardening: reject unknown keys on create, close the `data`-key bypass, promote `percentage_of_reference_year` to an explicit field, revisit `status` settability and the planner/embodied-energy exemptions. First inventory every FE-sent key not in a Create DTO (`power_w`, kwh fields, `room_surface_square_meter`, …). | F-5, F-6, F-7             | **lead sign-off** — permission scoping                                            |
| **S6** | Frontend config parity: required flags, min/max bounds, drop the 0.001 minimums (or confirm them), integer check for `int` fields, trim before required. Mechanical edits to `module-config/*.ts` + the shared validator only.                                                                                                                  | F-8, F-9                  | none                                                                              |
| **S7** | Frontend↔backend contract test, phase (a): a backend script exports effective DTO constraints (required/type/enum/range) to a committed JSON fixture + a freshness test; a frontend Playwright unit spec (existing `tests/unit` pure-function pattern) walks `MODULES_CONFIG` against it. No CI plumbing.                                       | pins S6 permanently       | **async ack** — adjacent to ADR-020, but derived _from_ the backend so SSoT holds |
| **S8** | Real-backend Playwright e2e validation suite (needs CI postgres+backend, `/api` proxy for the preview server, `login-test`). Anchor: the `test.fixme` at `frontend/tests/integration/backoffice-config.spec.ts:408`.                                                                                                                            | —                         | **parked with the lead**, like F-11, F-12 and the doc-automation bonus            |

## Verification of this slice

```bash
make build-docs                                   # docs build with this file
cd backend && uv run pytest tests/unit/modules/ tests/unit/services/data_ingestion/ -q
                                                  # 433 passed — audit baseline
git diff --stat origin/dev...HEAD -- ':!docs'     # empty — docs-only PR
```
