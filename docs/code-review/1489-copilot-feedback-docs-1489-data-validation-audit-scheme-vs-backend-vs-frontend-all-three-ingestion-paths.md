# Bot Review TODOs: PR #2204

Source Branch: `docs/1489-data-validation-audit`
---

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Adds a new implementation-plan document for #1489 that audits the documented data-validation “scheme” against current backend/frontend enforcement across all three ingestion paths, and proposes an ordered set of follow-up hardening slices (S1–S8).

**Changes:**

- Introduces a rule-by-rule audit matrix comparing doc vs backend vs frontend behavior for reference/factor CSVs, entry CSVs, and form input.
- Documents reproduced evidence chains (notably #1545) and consolidates gaps into a numbered findings list with proposed follow-up slices.
- Provides a doc-stale report section intended for the data manager (items to update in docs rather than code).

---

💡 <a href="/EPFL-ENAC/co2-calculator/new/dev?filename=.github/skills/code-review/SKILL.md" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Add a `code-review` agent skill</a> or configure MCP servers for context-aware, tailored reviews. <a href="https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review#mcp-servers-and-agent-skills" class="Link--inTextBlock" target="_blank" rel="noopener noreferrer">Learn more in the docs.</a>
---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 1 out of 1 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (1)</summary>

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:287**

- The verification snippet runs backend tests via `cd backend && uv run pytest ...`, which conflicts with the repo’s documented convention to run lint/type-check/test from the repo root via `make` targets (see `AGENTS.md`). Using `make test` also ensures the same tooling/flags are used consistently.

```
cd backend && uv run pytest tests/unit/modules/ tests/unit/services/data_ingestion/ -q
                                                  # 433 passed — audit baseline
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 1 out of 1 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (1)</summary>

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:14**

- The frontmatter `summary` is a multi-line double-quoted scalar. `docs/gen_indexes.py` injects `meta["summary"]` directly into a Markdown table row (only escaping `|`), so embedded newlines will break the generated `implementation-plans/index.md` table formatting.

```
summary:
  "Slice 1 of #1489: a systematic audit of every documented data rule (back-office
  doc site, data-description pages) against actual backend enforcement, frontend
  enforcement, and test coverage, across the three ingestion paths (back-office
  reference/factor CSVs, entry CSVs, direct form input). Every claim was re-verified by
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 1 out of 1 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (24)</summary>

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:298**

- The S2 scope promises a `row error` for reference-data numeric failures, but `_to_float` runs inside the building-rooms ingest, which has no `row_errors` accumulator; raising there produces a job-level failure rather than an entry in the existing row-error channel. Either call this an upload error or include the additional reference-ingest error plumbing in S2.

```
| **S2**     | Factor providers persist `validate_create`'s validated output; unparseable numerics = row error, not raw-string passthrough — in both `_convert_value` (factors) and `_to_float` (reference data, the F-2 residual).                                                                                                                            | F-2, F-3                  | **PR #2231**                                                                        |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:14**

- The frontmatter summary still says the follow-up sequence is starting with the #1545 silent-wipe fix, while this document says #2216 shipped S1 and the next planned work is S2/#2231. Please update the summary so the plan's top-level status agrees with its re-baseline and slice table.

```
  ends in an ordered set of small follow-up PRs, starting with the #1545 reference-CSV
  silent-wipe hole. The cross-repo doc-change automation bonus is parked."
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:303**

- The proposed exporter cannot derive all of the audited effective rules from the current DTO schema metadata: several ranges and cross-field rules live only in imperative `field_validator`/`model_validator` methods (for example, headcount FTE), not in required/type/enum/range declarations. A fixture generated from those four metadata categories would therefore omit constraints that S6 is meant to pin. Define explicit machine-readable constraint metadata or include validator probes in S7 before treating this as a complete contract test.

```
| **S7**     | Frontend↔backend contract test, phase (a): a backend script exports effective DTO constraints (required/type/enum/range) to a committed JSON fixture + a freshness test; a frontend Playwright unit spec (existing `tests/unit` pure-function pattern) walks `MODULES_CONFIG` against it. No CI plumbing.                                       | pins S6 permanently       | **async ack** — adjacent to ADR-020, but derived _from_ the backend so SSoT holds   |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:107**

- `process_emissions.ts` declares `subcategory` with `required: true` (lines 25–30), so the frontend is not an “optional select” as this row states. The generic validator may skip a subkind with no options, but where options exist the current frontend requires it for every category, unlike the backend's optional field.

```
| subcategory | optional; **required for Refrigerants** | optional — conditional rule **nowhere** at DTO level                                   | optional select                                                                        | **?** — conditional enforced only implicitly at factor resolution, silently (F-11/D-5) |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:144**

- The current `resolve_clouds` and `resolve_ai` implementations raise `EmissionTypeResolutionError` for unknown service types/providers, and #2091 escalates that out of row processing. These rows therefore should not describe unknown values as silently missing at factor resolution or label them as the current F-11 behavior; reserve F-11 for the residual lookup/compute branches.

```
| service_type (cloud)           | storage \| compute                 | plain `str` — **no enum**; match happens at factor resolution (silent on miss, F-11)                                                                  | select, required ✅      | **GAP-BE** (F-10)                                         |
| provider                       | within factors                     | plain `str`, same                                                                                                                                     | select, required ✅      | OK-ish (F-11)                                             |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:176**

- The common RF validators cited here only reject `None`; they convert values to strings but do not reject `''` or whitespace-only IDs/names. Calling these fields “non-empty” and marking the row OK contradicts `research_facilities/data_entries.py:36-48` and the later F-10 finding.

```
| researchfacility_id / name                         | required, within factors | required, non-empty (common: `:36-48`)                                                         | name select required; id derived                               | OK                        |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:293**

- The text says every slice is one PR, but S2, S4, and S6 all point to the same PR #2231. That PR's description explicitly groups those three ungated fixes in one PR, so the stated delivery model is inconsistent with the table. Clarify that those slices are grouped (or change the gates).

```
Ordered; each is one small PR to `dev` with its own regression test. S1–S2 are
independent and can go in parallel. This audit is **S0** (docs only).
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:310**

- This verification snippet uses `cd backend && ...` for a test command, contrary to the repository guardrail that root `make` targets are canonical for tests (see `Makefile:39-44` and the internal contributing rules). Either document the canonical root target or explicitly label this as a targeted baseline probe alongside the canonical verification command.

```
cd backend && uv run pytest tests/unit/modules/ tests/unit/services/data_ingestion/ -q
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:36**

- The method cites a committed fixture at `backend/INPUT_DATA/...`, but that path is not present in this checkout (there is no `backend/INPUT_DATA` directory); the current #1545 regression test builds the CSV inline at `backend/tests/unit/services/data_ingestion/csv_providers/test_reference_data.py:84-97`. Please cite the inline test or add the fixture before claiming it was replayed.

```
`backend/INPUT_DATA/building_rooms_reference_test_wrong_column_name.csv` through
`ReferenceDataCSVProvider._validate_headers`, and a green run of the relevant suites
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:62**

- This cell overstates the current end-to-end behavior. The two cited tests exercise the handler directly (`[]`/`None`), but `DataEntryEmissionService` now wraps a `None` formula result and raises at `data_entry_emission_service.py:667-681,998-1036`; qualify this as a handler-level residual or show a still-silent service path.

```
| …and at compute time                                           | —                                                                                                  | —                                                                                                                                                                          | —                                                                                                                                             | ⚠️ a factor/unit mismatch yields **silently empty computations** — pinned by `test_resolve_computations_without_factor_id_returns_empty`, `test_unit_mismatch_between_entry_and_factor_returns_none` → **F-11** | —                                                                     |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:126**

- `EnergyCombustionBase` does not exist in the current backend, so this evidence link is not verifiable. The relevant create class is `EnergyCombustionHandlerCreate` at `backend/app/modules/buildings/data_entries.py:129-139`; keep the missing-`unit` conclusion but correct the class name.

```
| unit     | **required**, SI format      | **no `unit` field on the Create DTO at all** (only on `EnergyCombustionBase`) — a CSV `unit` column is dropped | text, not required      | **?** (D-6) — doc requires a column the backend cannot accept |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:89**

- This range is stale after the re-baseline: the current shared validator starts at `ModuleForm.vue:937` and its min/max logic runs through `:1092`, so `931-1059` omits the numeric checks this audit relies on. Update the anchor.

```
`ModuleForm.vue:931-1059`. Every module additionally inherits **F-5/F-6** (unknown-key
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:108**

- The cited frontend line is no longer the minimum: `process_emissions.ts:57` is the `kg_co2eq` field, while `min: 0.001` is at `process_emissions.ts:51`. Because this is an evidence table, update the reference.

```
| quantity_kg | required, ≥ 0                           | required, ≥ 0 (`:24-29`; tested)                                                       | required, **min 0.001** (`process_emissions.ts:57`) — forbids the 0 the backend allows | **DIV** (F-9)                                                                          |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:135**

- The `equipment.ts:72-73` anchor points to the label fields, not `required`/`min`; those are at lines 75-76 in the current file. Update the citation so the claimed frontend drift can be verified.

```
| sub_class                           | optional, class/subclass tuple in factors | optional                                          | **required: true** + stray `min: 0` on a select (`equipment.ts:72-73`)                                                        | **DIV** (F-8)                       |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:167**

- The 9-value list is not at `purchase/data_entries.py:84-100`; it is defined in `backend/app/utils/currencies.py:3-5` and the DTO imports it. Update the evidence pointer.

```
| currency                                  | optional; chf/eur/usd/gbp/aud, default chf | optional, default chf, **9-value list** aud/cad/chf/cny/eur/gbp/jpy/sek/usd (`:84-100`); the code even carries the comment _"doc say mandatory, but with default -> optional"_ (`:37`) | optional select                                  | **DOC-STALE** (D-2)  |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:164**

- F-10 is defined here as a code gap for whitespace-only required strings, so this row cannot be labeled `OK` while it explicitly says the backend has no strip check. Use the same gap verdict as the process-emissions row or explain a different definition of “non-empty.”

```
| name                                      | required, non-empty                        | required (no strip check)                                                                                                                                                              | required ✅                                      | OK (F-10 whitespace) |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:220**

- The filter is not the only path: `kg_co2eq` is intentionally read from raw rows at `base_csv_provider.py:1217-1228`, and `unit_institutional_id` is also consumed outside the filter at `:1261-1287`. S3 must allowlist these valid control columns before rejecting “unknown” headers, or it will break existing imports.

```
  providers but set nowhere; unknown columns are silently dropped by `filtered_row`
  (`base_csv_provider.py:1234-1239`); and CSV columns literally named `data` or
  `status` survive the filter because both are DTO fields (probe: both in
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:299**

- Header validation does not currently use `row_errors`: `BaseCSVProvider.process_csv_in_batches` catches `ValueError` from `_validate_csv_headers` and writes a job-level `validation_error` at `base_csv_provider.py:1156-1172`. Either keep that surface or explicitly plan the new mapping; do not describe it as an existing `row_errors` channel.

```
| **S3**     | Entry-CSV strict columns: reject unknown columns (incl. `data`/`status`), validate the full header not a 5-row sample — smallest diff wins (likely: enable + harden `strict_column_validation`); surface through the existing `row_errors` channel.                                                                                             | F-4                       | **lead heads-up** — flips a default for all entry ingestion                         |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:61**

- The P1b cell is stale relative to F-3 below and the current provider: after #2091, an unmappable emission type raises out of row processing and aborts the whole factor upload; it is no longer merely a row failure. Please describe the upload-level failure here so the matrix does not contradict its own update note.

```
| Referential integrity (category/class/code must match factors) | n/a                                                                                                | ✅ `get_factor_emission_type_id` fails the row                                                                                                                             | fail-fast when factors absent (`_guard_factors_required`, `:154-186`)                                                                         | not at DTO level                                                                                                                                                                                                | n/a                                                                   |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:64**

- This current-state matrix still reports the pre-#2216 reference path (`SUCCESS` after NULLing rows) even though the document says F-1 is fixed and S1 is done. Unknown-header failures now happen before deletion; only malformed row values still reach the delete/reinsert behavior. Please distinguish the historical #1545 behavior from these remaining F-2 semantics here.

```
| Failure surface                                                | job SUCCESS with full `rows_inserted` even when every surface is NULL → **F-1**                    | job `row_errors` in meta (capped at 100)                                                                                                                                   | job `row_errors` / SSE                                                                                                                        | four different error envelopes (`detail:str`, `{code,fields}`, `{errors:[...]}`, FastAPI list) → **F-12** (recorded, deferred)                                                                                  | `422 {"detail":{"errors":[...]}}` — all rows, all errors              |
| Destructive semantics                                          | ⚠️ building-rooms ingest is **delete-then-reinsert** (`:495-538`) — one bad upload wipes the table | per-type delete before ingest                                                                                                                                              | re-upload semantics (tested)                                                                                                                  | n/a                                                                                                                                                                                                             | n/a                                                                   |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:225**

- `unflatten_payload` puts unknown keys into the persisted `data` object, so `note` → `notes` does not lose the value; it stores it under the wrong key, and consumers reading the declared `note` field will not see it. Please describe this as mis-keyed persistence rather than data loss.

```
  it. A typo on an optional field (`note` → `notes`) silently loses the value.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:230**

- The route cited here resolves a write scope and calls `check_module_permission_for_report(..., action="edit")` before invoking the workflow. The bypass therefore applies to an authenticated user with module edit permission, not to any authenticated user; overstating the authorization boundary makes the security impact inaccurate.

```
  (`carbon_report_module.py:844`), so any authenticated user can write arbitrary JSON
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:40**

- There are no `Tests` columns in the matrix or per-module tables below; the file only contains inline test references. This wording makes the claimed audit method hard to reproduce. Please refer to “test references below” (or add the promised columns).

```
passed). Probe scripts were throwaway (session scratchpad, not committed). The _Tests_
columns record rule-level test existence found by inspection, not mutation-verified
coverage.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:212**

- The discarded DTO is a real gap, but the stated persisted outcome is not: `_process_row` returns on `ValidationError` at `base_factor_csv_provider.py:399-408`, before `prepare_create` receives `values`. An unparseable optional numeric therefore cannot land as a raw string in `Factor.values`; describe the loss of normalization for rows that do pass validation instead.

```
  typo'd optional numeric lands as a string in `Factor.values`. _Update 2026-08-20:_
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 1 out of 1 changed files in this pull request and generated 2 comments.

<details>
<summary>Suppressed comments (17)</summary>

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:46**

- `39a5dcdb` cannot be the current re-baseline while this file also records #2231 as merged and the checkout contains its fixes. In particular, the following findings still call F-2/F-3/F-7 open. Please update the baseline and re-run/status the audit so all sections describe one code state.

```
**Re-baselined 2026-08-20** against `dev` at `39a5dcdb` (95 commits landed while this
audit was in review). Every probe was re-run at the new HEAD. Material changes:
**F-1 is fixed** (#2216 makes unknown reference-CSV columns a hard error, with a
regression test on the #1545 fixture), and the #2091 / #2050 / #1186 series removed
several of the silent-degradation paths F-11 pointed at. F-2 (residual), F-3 (mostly),
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:63**

- This reference-CSV failure surface is historical after #2216: the header check now raises before the delete/reinsert. Leaving “job SUCCESS ... NULL” beside the hard-error status in line 56 makes the matrix self-contradictory; label this cell as pre-#2216 or update it.

```
| Failure surface                                                | job SUCCESS with full `rows_inserted` even when every surface is NULL → **F-1**                    | job `row_errors` in meta (capped at 100)                                                                                                                                   | job `row_errors` / SSE                                                                                                                        | four different error envelopes (`detail:str`, `{code,fields}`, `{errors:[...]}`, FastAPI list) → **F-12** (recorded, deferred)                                                                                  | `422 {"detail":{"errors":[...]}}` — all rows, all errors              |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:100**

- These rows still report the pre-S6 frontend configuration. At the current head, `headcount.ts` sets `required: true` for `name`, `sius_code`, member `fte`, and student `fte` (with member `fte` min/max), so the listed GAP-FE values are no longer true. Rebaseline this block while retaining only residual differences.

```
| name                  | required, non-empty    | required, non-empty, stripped (`:32-39`; test pins strip)           | **not required** (`headcount.ts:24-26`) | **GAP-FE** (F-8)                                  |
| sius_code             | required, values 51–59 | required, enum `{51,52,53,54,56,57,58,59}` (`:9`) — **55 excluded** | select, **not required**                | **GAP-FE** (F-8) + **DOC-STALE** on 55 (D-3)      |
| user_institutional_id | required, numbers only | required, non-empty (`:41-47`) — no numbers-only check              | required ✅                             | **DIV** minor: digits-only unenforced BE+FE (F-9) |
| fte (member)          | required, 0 ≤ v ≤ 1    | required, 0–1 (`:49-58`)                                            | min 0 / max 1, **not required**         | **GAP-FE** (F-8)                                  |
| fte (student)         | (same table) 0 ≤ v ≤ 1 | required, **≥ 0 only — no upper bound** (`:72-77`)                  | min 0, not required                     | **GAP-FE** + **?** upper bound (D-4)              |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:117**

- The current frontend config already marks `room_type` required and constrains `room_allocation_ratio` to 0–1. These GAP-FE entries are stale despite S6 being marked merged below; update them to the current behavior.

```
| room_type                                | required, 6-value enum     | **required**, enum matches doc (`:48-56, :81-87`)                                       | select, **not required** (`buildings.ts:39-41`) | **GAP-FE** (F-8)                    |
| room_allocation_ratio                    | optional, 0 ≤ v ≤ 1        | optional, 0–1 (`:89-93`)                                                                | number, **no min/max** (`buildings.ts:79-92`)   | **GAP-FE** (F-8)                    |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:106**

- At the current head, `ProcessEmissionsHandlerCreate` rejects whitespace-only `category` via its `_non_empty` validator, so this GAP-BE verdict is stale. Re-run or update this row after #2231.

```
| category    | required, must match factors            | required (match at factor resolution — see F-11); **whitespace-only accepted** (probe) | select, required ✅                                                                    | **GAP-BE** whitespace (F-10)                                                           |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:164**

- `PurchaseHandlerCreate` now has a `_non_empty` validator for `name` (`purchase/data_entries.py:36-41`), so “no strip check” and the F-10 tag are stale for this field. If F-10 refers to `purchase_institutional_code` instead, name that field explicitly.

```
| name                                      | required, non-empty                        | required (no strip check)                                                                                                                                                              | required ✅                                      | OK (F-10 whitespace) |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:170**

- The current `purchase.ts` config marks centralized `coef_to_kg` as required with `min: 0`, so this GAP-FE row is also pre-S6. It conflicts with the S6 “merged” status and should be rebaselined.

```
| centralized: coef_to_kg                   | required                                   | required, ≥ 0 (`:111-115`)                                                                                                                                                             | **not required, no min** (`purchase.ts:137-139`) | **GAP-FE** (F-8)     |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:179**

- The common research-facilities frontend fields are now numeric/required (`research-facilities.ts`), and `ResearchFacilitiesAnimalHandlerCreate` now validates required/non-empty fields and rejects negative `use` (`data_entries.py:116-153`). These rows retain the pre-#2231 gaps; rebaseline the common and animal portions separately.

```
| researchfacility_id / name                         | required, within factors | required, non-empty (common: `:36-48`)                                                         | name select required; id derived                               | OK                        |
| use (common)                                       | required, ≥ 0            | required, numeric, ≥ 0 (`:50-58`)                                                              | **type 'text', not required** (`research-facilities.ts:24-26`) | **GAP-FE** (F-8)          |
| use_unit                                           | required, within factors | required (common)                                                                              | text, not required                                             | **GAP-FE** (F-8)          |
| **animal:** researchfacility_type / use / use_unit | required; use ≥ 0        | fields required but **zero validators** — `use = -5` **accepted** (probe), no non-empty checks | not required either                                            | **GAP-BE** (F-7) + GAP-FE |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:231**

- The access-control scope is overstated here. The create route resolves the write scope and checks `action="edit"` before accepting `item_data`, so this bypass is reachable by users authorized to edit the report/module, not by any authenticated user. Please state that condition accurately.

```
- **F-6 · code-gap · S5** — A client-supplied `data` key **bypasses field validation
  entirely**: with valid declared fields alongside, validation passes on those, then
  the arbitrary `data` dict is what persists (probe:
  `data == {'totally': 'arbitrary'}`). The create route takes `item_data: dict`
  (`carbon_report_module.py:844`), so any authenticated user can write arbitrary JSON
  into `data_entries.data`.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:237**

- The animal-DTO portion of F-7 is stale: the current `ResearchFacilitiesAnimalHandlerCreate` validators reject negative `use` and enforce the required/non-empty fields. Keep any update-policy issue that remains, but remove or reclassify this pre-#2231 claim.

```
  `status` is a settable DTO field on exempt paths. Also at DTO level:
  `ResearchFacilitiesAnimalHandlerCreate` has **no validators** — `use = -5` is
  accepted (probe) while the common-RF DTO rejects it.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:242**

- Several F-8 examples have already been fixed in the current frontend config: headcount required flags, building `room_type`/ratio bounds, research-facility `use`/`use_unit`, and centralized-purchase `coef_to_kg`. These should not remain listed as open gaps; leave only the current residual mismatches.

```
- **F-8 · code-gap (FE) · S6** — Frontend config misses backend rules: headcount
  `name`/`sius_code`/`fte` not required; buildings `room_type` not required and
  `room_allocation_ratio` unbounded; RF `use` is an optional _text_ field;
  centralized-purchase `coef_to_kg` optional/unbounded; conversely `sub_class`,
  usage-hours and `power_w` are _stricter or absent-in-DTO_ on the frontend.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:246**

- Only part of F-9 remains as written: `ModuleForm.vue` now treats `(typeof v === 'string' && v.trim() === '')` as empty for required fields, so “FE never trims before its required check” is false. Separate that fixed behavior from the still-open minimum, integer, and digits-only items.

```
- **F-9 · code-gap (both) · S4+S6** — Cross-cutting rule drift: FE `min: 0.001` where
  BE/doc allow 0 (`quantity_kg`, buildings `quantity`); no integer check FE-side for
  `int` fields (1.5 passes FE, 400s BE); `user_institutional_id` digits-only
  unenforced anywhere; FE never trims before its required check.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:283**

- This source citation is off at the current checkout: `purchase/data_entries.py:37` is `@classmethod`; the deliberate currency comment is at line 46. Correct the reference so D-2 can be verified.

```
| D-2 | purchase `currency`; AI `fte_count`     | 5 currencies; fte ≥ 1     | 9 currencies (adds cad/cny/jpy/sek); fte ≥ 0.1                                                                | explicit lists/validators, comment at `purchase/data_entries.py:37`                                                   |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:300**

- Section E marks S4 as merged, but Sections B/C still claim that the animal DTO has no validators and that process/purchase/building/cloud/travel required strings accept whitespace. The current animal DTO has validators in `data_entries.py:124-153`, and the whitespace regression tests cover these modules. Please mark these as pre-#2231 findings or update them to the current behavior.

```
| **S4**     | Backend DTO consistency fixes: animal-RF validators (use ≥ 0, non-empty ids), whitespace-strip on required strings everywhere, digits-only `user_institutional_id` (if confirmed).                                                                                                                                                              | F-7 (DTO part), F-9, F-10 | ✅ merged in #2231 (v1.4.0)                                                                       |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:230**

- The cited evidence location is no longer valid: `carbon_report_module.py` currently has 521 lines and `create()` starts at line 152, so line 844 cannot be followed. Update this anchor so the F-6 evidence remains reproducible.

```
  (`carbon_report_module.py:844`), so any authenticated user can write arbitrary JSON
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:40**

- The method claims that “Tests columns” record rule-level test existence, but the matrices below contain no Tests column. That leaves the stated test-coverage audit unavailable to readers and makes the methodology inaccurate; add the test-status data or revise this claim to describe the evidence actually included.

```
passed). Probe scripts were throwaway (session scratchpad, not committed). The _Tests_
columns record rule-level test existence found by inspection, not mutation-verified
coverage.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:126**

- `EnergyCombustionBase` does not exist in the current backend; the relevant classes are `EnergyCombustionHandlerCreate` and `EnergyCombustionHandlerResponse`. The conclusion about `unit` being absent from the Create DTO is valid, but this stale class reference makes the audit hard to verify. Update the citation to the current DTOs.

```
| unit     | **required**, SI format      | **no `unit` field on the Create DTO at all** (only on `EnergyCombustionBase`) — a CSV `unit` column is dropped | text, not required      | **?** (D-6) — doc requires a column the backend cannot accept |
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 1 out of 1 changed files in this pull request and generated no new comments.

<details>
<summary>Suppressed comments (26)</summary>

**Previously missed (4)** — in code that hasn't changed since the last review.

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:144**

- F-1's failure surface is no longer current: `_validate_headers` now raises for unexpected headers before `_ingest_building_rooms` executes its delete. This row should describe the pre-#2216 behavior as historical (or mark it fixed), not claim a successful upload currently NULLs every surface.

This issue also appears in the following locations of the same file:

- line 156
- line 307

```
| Failure surface                                                | job SUCCESS with full `rows_inserted` even when every surface is NULL → **F-1**                    | job `row_errors` in meta (capped at 100)                                                                                                                                   | job `row_errors` / SSE                                                                                                                        | four different error envelopes (`detail:str`, `{code,fields}`, `{errors:[...]}`, FastAPI list) → **F-12** (recorded, deferred)                                                                                  | `422 {"detail":{"errors":[...]}}` — all rows, all errors              |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:181**

- These frontend values are stale after #2231: the current `headcount.ts` marks member `name`, `sius_code`, and `fte` as required, and student `fte` as required; member `fte` also has min/max bounds. Because S6 is marked merged below, update these rows instead of reporting the completed changes as an open GAP-FE.

This issue also appears in the following locations of the same file:

- line 197
- line 251
- line 258
- line 317
- line 319
- ...and 1 more

```
| name                  | required, non-empty    | required, non-empty, stripped (`:32-39`; test pins strip)           | **not required** (`headcount.ts:24-26`) | **GAP-FE** (F-8)                                  |
| sius_code             | required, values 51–59 | required, enum `{51,52,53,54,56,57,58,59}` (`:9`) — **55 excluded** | select, **not required**                | **GAP-FE** (F-8) + **DOC-STALE** on 55 (D-3)      |
| user_institutional_id | required, numbers only | required, non-empty (`:41-47`) — no numbers-only check              | required ✅                             | **DIV** minor: digits-only unenforced BE+FE (F-9) |
| fte (member)          | required, 0 ≤ v ≤ 1    | required, 0–1 (`:49-58`)                                            | min 0 / max 1, **not required**         | **GAP-FE** (F-8)                                  |
| fte (student)         | (same table) 0 ≤ v ≤ 1 | required, **≥ 0 only — no upper bound** (`:72-77`)                  | min 0, not required                     | **GAP-FE** + **?** upper bound (D-4)              |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:188**

- The current code disagrees with both claims here: `ProcessEmissionsHandlerCreate` rejects a whitespace-only `category`, and `process_emissions.ts` sets `subcategory` to `required: true`. Re-baseline this pair; the table currently preserves pre-#2231 behavior.

This issue also appears on line 245 of the same file.

```
| category    | required, must match factors            | required (match at factor resolution — see F-11); **whitespace-only accepted** (probe) | select, required ✅                                                                    | **GAP-BE** whitespace (F-10)                                                           |
| subcategory | optional; **required for Refrigerants** | optional — conditional rule **nowhere** at DTO level                                   | optional select                                                                        | **?** — conditional enforced only implicitly at factor resolution, silently (F-11/D-5) |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:207**

- The cited `EnergyCombustionBase` symbol does not exist in this checkout. `unit` is declared on `EnergyCombustionFactorCreate` (`buildings/factors.py:150-155`) and the response DTO, while `EnergyCombustionHandlerCreate` omits it. Correcting this reference is important because the planned follow-up otherwise points maintainers to a nonexistent class.

```
| unit     | **required**, SI format      | **no `unit` field on the Create DTO at all** (only on `EnergyCombustionBase`) — a CSV `unit` column is dropped | text, not required      | **?** (D-6) — doc requires a column the backend cannot accept |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:140**

- These two cells describe behavior already fixed in the current checkout. `reference_data._to_float` raises on a present invalid value (and its regression test covers `"12,5"`), while `BaseFactorCSVProvider` copies fields from the validated DTO into `values` before persistence. Both are also listed as merged in S2 below. Please re-baseline this row; otherwise the matrix contradicts the stated current status.

```
| Type-coercion failure                                          | ⚠️ `_to_float('abc') → None`, `_to_float(None) → None` — silent NULL (`:541-550`) → **F-2**        | ⚠️ `_convert_value` keeps the raw **string** for optional numerics (`:649-658`); DTO-validated output is **discarded** — hand-built dicts persisted (`:392-421`) → **F-3** | ✅ per-row DTO error, recorded in `row_errors`                                                                                                | ✅ rejected (`float_parsing`); numeric strings coerced (`'1.5' → 1.5`) — but coercion _failures_ fall through to pydantic silently at debug level (`data_entry.py:63-66`)                                       | ✅ per-row pydantic model, ranges enforced                            |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:160**

- The block is labeled as reproduced, but it is the pre-#2216 behavior. Current `_validate_headers` rejects this exact fixture at the unknown-column check, so it never reaches `_to_float` or delete. Please label the block historical and add the current hard-error outcome to keep it consistent with F-1.

```
_validate_headers(...)   → PASSES; logs only
  "WARNING Reference CSV has unexpected columns (ignored): room_surface_square_meters"
required set = {building_location, building_name, room_name}       ← surface not in it
_to_float(raw.get("room_surface_square_meter")) = _to_float(None) → None
delete(BuildingRoom); re-insert all rows with surface=NULL; flush  → job SUCCESS
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:198**

- Both frontend gaps are fixed in the current `buildings.ts`: `room_type` is `required: true`, and `room_allocation_ratio` has `min: 0` and `max: 1`. These rows should not remain marked GAP-FE while S6 is recorded as merged.

```
| room_type                                | required, 6-value enum     | **required**, enum matches doc (`:48-56, :81-87`)                                       | select, **not required** (`buildings.ts:39-41`) | **GAP-FE** (F-8)                    |
| room_allocation_ratio                    | optional, 0 ≤ v ≤ 1        | optional, 0–1 (`:89-93`)                                                                | number, **no min/max** (`buildings.ts:79-92`)   | **GAP-FE** (F-8)                    |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:245**

- The current `PurchaseHandlerCreate` has a `_non_empty` validator for `name`, and the whitespace regression suite covers it. The `no strip check` note and F-10 reference in this row are therefore stale and should be re-baselined.

```
| name                                      | required, non-empty                        | required (no strip check)                                                                                                                                                              | required ✅                                      | OK (F-10 whitespace) |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:251**

- The current `purchase.ts` marks centralized `coef_to_kg` as `required: true` with `min: 0`. This frontend gap was addressed by #2231/S6, so leaving it as GAP-FE makes the per-module table contradict the stated shipped status.

```
| centralized: coef_to_kg                   | required                                   | required, ≥ 0 (`:111-115`)                                                                                                                                                             | **not required, no min** (`purchase.ts:137-139`) | **GAP-FE** (F-8)     |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:260**

- These rows preserve pre-#2231 behavior: the common RF config currently uses a numeric, required `use` with `min: 0` and a required `use_unit`, and the animal Create DTO now validates non-negative `use` plus non-empty required strings. Re-baseline both the frontend and backend verdicts here rather than leaving S4's completed fixes reported as open.

```
| use (common)                                       | required, ≥ 0            | required, numeric, ≥ 0 (`:50-58`)                                                              | **type 'text', not required** (`research-facilities.ts:24-26`) | **GAP-FE** (F-8)          |
| use_unit                                           | required, within factors | required (common)                                                                              | text, not required                                             | **GAP-FE** (F-8)          |
| **animal:** researchfacility_type / use / use_unit | required; use ≥ 0        | fields required but **zero validators** — `use = -5` **accepted** (probe), no non-empty checks | not required either                                            | **GAP-BE** (F-7) + GAP-FE |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:306**

- Because `unflatten_payload` puts an unknown `notes` key into `data`, the value is not lost from the database; it remains under the wrong key and is ignored by module semantics. Please make this sentence consistent with the preceding claim that unknown keys are persisted.

```
  it. A typo on an optional field (`note` → `notes`) silently loses the value.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:311**

- “Bypasses all field validation” is too broad: `handler.validate_create` still validates the declared DTO fields; only the contents of a supplied `data` dict bypass module-field validation. Also, the create route performs authentication and module `edit` permission checks, so “any authenticated user” should be narrowed to an authenticated user with edit access.

```
- **F-6 · code-gap · S5** — A client-supplied `data` key **bypasses field validation
  entirely**: with valid declared fields alongside, validation passes on those, then
  the arbitrary `data` dict is what persists (probe:
  `data == {'totally': 'arbitrary'}`). The create route takes `item_data: dict`
  (`carbon_report_module.py:844`), so any authenticated user can write arbitrary JSON
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:318**

- The animal DTO no longer has “no validators”: its current validators reject negative `use` and blank required identifiers, with regression tests covering those cases. Since S4 is marked merged, remove this DTO sentence from the open F-7 finding or mark that part fixed while retaining any still-open permission concerns.

```
  `ResearchFacilitiesAnimalHandlerCreate` has **no validators** — `use = -5` is
  accepted (probe) while the common-RF DTO rejects it.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:323**

- Most of the missing frontend rules listed here are already present in the current configs: headcount required flags/bounds, building room requirements/bounds, RF numeric requirements, and centralized-purchase `coef_to_kg` were all fixed by #2231. Update F-8 to leave only genuinely unresolved differences; otherwise the aggregate finding contradicts the table's S6-merged status.

```
- **F-8 · code-gap (FE) · S6** — Frontend config misses backend rules: headcount
  `name`/`sius_code`/`fte` not required; buildings `room_type` not required and
  `room_allocation_ratio` unbounded; RF `use` is an optional _text_ field;
  centralized-purchase `coef_to_kg` optional/unbounded; conversely `sub_class`,
  usage-hours and `power_w` are _stricter or absent-in-DTO_ on the frontend.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:330**

- F-10 is stale in the current checkout: validators now reject whitespace-only required strings in process emissions, purchases, buildings, external cloud/AI, and travel, and `test_whitespace_required_strings.py` covers the create/update behavior. Mark this finding fixed or narrow it to any remaining uncovered fields; its open S4 status conflicts with the shipped changes.

```
- **F-10 · code-gap · S4** — Whitespace-only required strings: equipment, headcount
  and common-RF strip/reject; process_emissions (probe: `category: '   '` accepted),
  purchase and others don't. Inconsistent within one codebase.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:287**

- This finding is contradicted by the current implementation and regression test: `_to_float` returns `None` only for absent/blank/`-` values, and raises `ValueError` for a present unparseable value such as `12,5`. S2 is already marked merged below, so this should be marked fixed or reduced to any remaining issue rather than left as an open silent-NULL gap.

```
- **F-2 · code-gap · S2** — Still open after #2216: `_to_float`
  (`reference_data.py`) maps a _present but unparseable_ value to `None` silently —
  `_to_float('12,5') → None` (re-probed at `39a5dcdb`). A wrong decimal separator
  still NULLs data with no row error; only the column-name vector is closed.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:296**

- The current factor provider does not discard the validated result: after `handler.validate_create`, it copies each DTO field from `validated` back into `values` before persistence. The tests also pin this behavior. Please mark the discarded-DTO/raw-string issue fixed or describe only any residual behavior that remains after #2231.

```
- **F-3 · code-gap (partial) · S2** — Factor providers validate rows but persist the
  **unvalidated** hand-built dicts: `handler.validate_create(...)`'s return value is
  discarded (`base_factor_csv_provider.py:392-421` — the comment says "don't rely on
  validated DTO", mirroring `seed_generic_factors.py`), and `_convert_value` keeps raw
  strings when `float()` fails. DTO coercions/normalizations never reach the DB; a
  typo'd optional numeric lands as a string in `Factor.values`. _Update 2026-08-20:_
  #2091 hardened the adjacent step — an unmappable emission type now **aborts the
  whole upload** instead of skipping the row — but the discarded-DTO and
  raw-string-passthrough parts were re-checked and remain.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:214**

- The `OK` verdict misses the documented alphanumeric constraint: `EquipmentHandlerCreate` only checks `equipment_id` with `v.strip()` for emptiness (`equipment/data_entries.py:83-88`), so non-empty values such as `@@@` are accepted. Classify this as a backend gap or explicitly record the documentation as stale instead of calling the rules aligned.

```
| equipment_id                        | required, alphanumeric                    | required, non-empty after strip (`:83-88`)        | required ✅                                                                                                                   | OK                                  |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:238**

- The backend does not enforce the documented “required” rule here: both travel create DTOs declare `number_of_trips: int = 1` (`professional_travel/data_entries.py:105` and `:139`), so omission is accepted. This row should not be marked `OK` without explicitly qualifying the requirement or removing the default.

```
| number_of_trips                          | required int, ≥ 1                                | default 1, ≥ 1 (`:102-106,:132-136`)                                                                                                                    | required, min 1 (`professional-travel.ts:81-82`)             | **OK** — an earlier exploration claim that the form skips this was wrong; the config `min: 1` feeds the generic min check |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:327**

- The last clause is no longer true: the shared validator checks whitespace-only strings with `v.trim() === ''` (`ModuleForm.vue:1073-1078`). Keep the integer/minimum/user-ID observations if still valid, but remove or qualify “FE never trims before its required check.”

```
- **F-9 · code-gap (both) · S4+S6** — Cross-cutting rule drift: FE `min: 0.001` where
  BE/doc allow 0 (`quantity_kg`, buildings `quantity`); no integer check FE-side for
  `int` fields (1.5 passes FE, 400s BE); `user_institutional_id` digits-only
  unenforced anywhere; FE never trims before its required check.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:391**

- This verification block uses `cd backend && uv run pytest`, but the repository instructions require root `make` targets for lint/type-check/test commands (`AGENTS.md:30`). Use the canonical root-level invocation or document an approved root-level way to run this targeted suite so the plan does not contradict the repository workflow.

```
cd backend && uv run pytest tests/unit/modules/ tests/unit/services/data_ingestion/ -q
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:137**

- P1b explicitly reports that factor CSVs have no unknown-column check, but this known gap has no finding or follow-up slice; S3 only covers entry CSVs, while S2 covers numeric persistence. Either assign factor-header strictness to a slice or explain why extra factor columns are intentional, otherwise the audit leaves a stated validation hole unowned.

```
| Unknown column / key                                           | ✅ hard error since #2216 (was warn-only → **F-1**, fixed)                                         | ⚠️ no check at all                                                                                                                                                         | ⚠️ silently dropped by `filtered_row` (`:1234-1239`); columns named `data` or `status` **survive** the filter (they are DTO fields) → **F-4** | ⚠️ swept into persisted `data` — verified on **all 15** Create DTOs → **F-5**                                                                                                                                   | ⚠️ no unknown-column check (`missing = expected - actual` only)       |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:270**

- P4 is also documented as having no unknown-column check, but folding it into F-4/S3 does not assign a fix to the reduction-objective provider: F-4 and S3 are explicitly scoped to entry CSVs. Add P4 header strictness to a follow-up or document why those extra columns are intentionally accepted.

```
the pattern to copy. (Unknown columns still unchecked, folded into F-4's fix family.)
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:117**

- The referenced file is not present in this checkout (and no matching file exists under `backend/INPUT_DATA`). The #1545 regression test embeds the CSV text in `backend/tests/unit/services/data_ingestion/csv_providers/test_reference_data.py::test_validate_headers_rejects_unknown_columns` instead. Please cite that test or add the claimed fixture; otherwise the audit's primary evidence cannot be reproduced from the repository.

```
dict — all 15 module Create DTOs probed), a replay of the committed #1545 fixture
`backend/INPUT_DATA/building_rooms_reference_test_wrong_column_name.csv` through
`ReferenceDataCSVProvider._validate_headers`, and a green run of the relevant suites
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:127**

- This paragraph establishes a 39a5 pre-#2231 baseline, but Sections A–C do not consistently label their statements as historical: the #1545 trace still says the header check passes, the module matrix still reports the pre-fix frontend gaps, and F-2/F-3/F-10 still read as open even though section E says #2231 merged S2/S4/S6. Please add an explicit baseline label to those sections or update all findings to current status; otherwise readers cannot distinguish historical findings from residual gaps.

```
**Re-baselined 2026-08-20** against `dev` at `39a5dcdb` (95 commits landed while this
audit was in review). Every probe was re-run at the new HEAD. Material changes:
**F-1 is fixed** (#2216 makes unknown reference-CSV columns a hard error, with a
regression test on the #1545 fixture), and the #2091 / #2050 / #1186 series removed
several of the silent-degradation paths F-11 pointed at. F-2 (residual), F-3 (mostly),
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:170**

- The shared-validator citation ends at line 1059, before the current `validateField` required and numeric/range checks at lines 1066–1100. Since this range is offered as the evidence for the frontend verdicts, it points before the rules being audited; cite `validateField` or update the range and distinguish the historical commit if that is intentional.

```
`frontend/src/constant/module-config/<m>.ts` plus the shared validator
`ModuleForm.vue:931-1059`. Every module additionally inherits **F-5/F-6** (unknown-key
```

</details>

---

### Summary Feedback (copilot-pull-request-reviewer)

Copilot was unable to review this pull request because the user who requested the review has reached their quota limit.
---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

Copilot reviewed 1 out of 1 changed files in this pull request and generated 8 comments.

<details>
<summary>Suppressed comments (18)</summary>

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:161**

- This reproduction is now false as a current behavior: `_validate_headers` raises on the unexpected column after #2216. Label this chain explicitly as the pre-#2216 reproduction (or add the post-fix outcome), otherwise readers can conclude the trigger is still unfixed.

```
_validate_headers(...)   → PASSES; logs only
  "WARNING Reference CSV has unexpected columns (ignored): room_surface_square_meters"
required set = {building_location, building_name, room_name}       ← surface not in it
_to_float(raw.get("room_surface_square_meter")) = _to_float(None) → None
delete(BuildingRoom); re-insert all rows with surface=NULL; flush  → job SUCCESS
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:199**

- `buildings.ts` now sets `room_type.required: true` and `room_allocation_ratio.min/max` to 0/1. These are the S6 changes marked merged below, so this table should not retain the old GAP-FE verdicts.

```
| room_type                                | required, 6-value enum     | **required**, enum matches doc (`:48-56, :81-87`)                                       | select, **not required** (`buildings.ts:39-41`) | **GAP-FE** (F-8)                    |
| room_allocation_ratio                    | optional, 0 ≤ v ≤ 1        | optional, 0–1 (`:89-93`)                                                                | number, **no min/max** (`buildings.ts:79-92`)   | **GAP-FE** (F-8)                    |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:246**

- `PurchaseHandlerCreate` now has the `_non_empty` validator on `name` (`backend/app/modules/purchase/data_entries.py:36-41`), so "no strip check" and the F-10 note here are stale. If `purchase_institutional_code` is the remaining whitespace gap, document that field separately rather than attributing it to `name`.

```
| name                                      | required, non-empty                        | required (no strip check)                                                                                                                                                              | required ✅                                      | OK (F-10 whitespace) |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:261**

- This RF row is also pre-#2231: the current common config uses numeric required `use` with `min: 0` and required `use_unit`, while `ResearchFacilitiesAnimalHandlerCreate` validates non-negative use and all required strings. Rework the row so it does not contradict the S4-shipped status.

```
| use (common)                                       | required, ≥ 0            | required, numeric, ≥ 0 (`:50-58`)                                                              | **type 'text', not required** (`research-facilities.ts:24-26`) | **GAP-FE** (F-8)          |
| use_unit                                           | required, within factors | required (common)                                                                              | text, not required                                             | **GAP-FE** (F-8)          |
| **animal:** researchfacility_type / use / use_unit | required; use ≥ 0        | fields required but **zero validators** — `use = -5` **accepted** (probe), no non-empty checks | not required either                                            | **GAP-BE** (F-7) + GAP-FE |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:288**

- F-2 is no longer open as written: current `reference_data._to_float` returns `None` only for absent/blank/`-` values and raises for a present unparseable value (`backend/app/services/data_ingestion/csv_providers/reference_data.py:542-555`). Update this finding and the matrix's matching claim after #2231.

```
- **F-2 · code-gap · S2** — Still open after #2216: `_to_float`
  (`reference_data.py`) maps a _present but unparseable_ value to `None` silently —
  `_to_float('12,5') → None` (re-probed at `39a5dcdb`). A wrong decimal separator
  still NULLs data with no row error; only the column-name vector is closed.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:293**

- F-3 likewise describes the pre-#2231 implementation. `base_factor_csv_provider.py` now copies each validated DTO field back into `values` before `prepare_create` (`:410-420`), so the validated return is not discarded and typed bad numerics no longer reach persistence as raw strings. Rewrite this finding around any residual behavior that remains.

```
- **F-3 · code-gap (partial) · S2** — Factor providers validate rows but persist the
  **unvalidated** hand-built dicts: `handler.validate_create(...)`'s return value is
  discarded (`base_factor_csv_provider.py:392-421` — the comment says "don't rely on
  validated DTO", mirroring `seed_generic_factors.py`), and `_convert_value` keeps raw
  strings when `float()` fails. DTO coercions/normalizations never reach the DB; a
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:324**

- The first half of F-8 is stale after #2231: the current configs add the required flags/bounds for headcount, buildings, research facilities, and centralized purchase. The remaining frontend-only differences may still belong here, but the shipped fixes should not continue to be reported as gaps.

```
- **F-8 · code-gap (FE) · S6** — Frontend config misses backend rules: headcount
  `name`/`sius_code`/`fte` not required; buildings `room_type` not required and
  `room_allocation_ratio` unbounded; RF `use` is an optional _text_ field;
  centralized-purchase `coef_to_kg` optional/unbounded; conversely `sub_class`,
  usage-hours and `power_w` are _stricter or absent-in-DTO_ on the frontend.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:331**

- F-10 still reports the pre-#2231 probes: current process, purchase `name`, building, cloud/AI, and travel required-string validators reject whitespace, and the RF DTOs were fixed separately. Rewrite this finding to distinguish those shipped fixes from residual fields such as purchase institutional code or system-managed embodied-energy rows.

```
- **F-10 · code-gap · S4** — Whitespace-only required strings: equipment, headcount
  and common-RF strip/reject; process_emissions (probe: `category: '   '` accepted),
  purchase and others don't. Inconsistent within one codebase.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:382**

- S4 is marked fully merged, but the current DTO set still accepts whitespace-only `purchase_institutional_code` (the validator only checks `len`) and `BuildingEmbodiedEnergyHandlerCreate.room_name` has no non-empty validator. Either define these types as explicitly out of S4's scope or keep the residual validation gap visible in the slice status.

```
| **S4**     | Backend DTO consistency fixes: animal-RF validators (use ≥ 0, non-empty ids), whitespace-strip on required strings everywhere, digits-only `user_institutional_id` (if confirmed).                                                                                                                                                              | F-7 (DTO part), F-9, F-10 | ✅ merged in #2231 (v1.4.0)                                                                       |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:122**

- The method section says that “Tests” columns record rule-level test existence, but this document contains no Tests column in the matrix or any per-module table. As written, the claimed test evidence is not visible to readers; add the columns or correct this description.

```
passed). Probe scripts were throwaway (session scratchpad, not committed). The _Tests_
columns record rule-level test existence found by inspection, not mutation-verified
coverage.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:129**

- This re-baseline is stale relative to the current status stated above: #2231 is described as merged, and the checked-out code now raises for invalid reference numerics and copies DTO-normalized factor fields. Saying F-2/F-3 remain open at the current `last_updated` date makes the audit self-contradictory. Re-baseline this paragraph and all dependent tables/findings, or explicitly label it as historical evidence.

```
audit was in review). Every probe was re-run at the new HEAD. Material changes:
**F-1 is fixed** (#2216 makes unknown reference-CSV columns a hard error, with a
regression test on the #1545 fixture), and the #2091 / #2050 / #1186 series removed
several of the silent-degradation paths F-11 pointed at. F-2 (residual), F-3 (mostly),
F-4, F-5, F-6, F-7 were re-verified **still open** at `39a5dcdb`.
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:141**

- These type-coercion cells still describe the pre-#2231 implementation: the current `reference_data._to_float` raises on a present value such as `12,5`, and `base_factor_csv_provider` copies validated DTO fields into `values`. Keeping the old behavior in the core matrix contradicts the “already fixed” section; update the cells or mark this matrix as historical.

```
| Type-coercion failure                                          | ⚠️ `_to_float('abc') → None`, `_to_float(None) → None` — silent NULL (`:541-550`) → **F-2**        | ⚠️ `_convert_value` keeps the raw **string** for optional numerics (`:649-658`); DTO-validated output is **discarded** — hand-built dicts persisted (`:392-421`) → **F-3** | ✅ per-row DTO error, recorded in `row_errors`                                                                                                | ✅ rejected (`float_parsing`); numeric strings coerced (`'1.5' → 1.5`) — but coercion _failures_ fall through to pydantic silently at debug level (`data_entry.py:63-66`)                                       | ✅ per-row pydantic model, ranges enforced                            |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:271**

- The matrix identifies P4 unknown columns as an open hole, but F-4/S3 are explicitly scoped to P2 entry CSVs and `validate_reduction_objective_csv` uses a separate header path. No follow-up row currently owns this P4 gap. Include reduction-objective headers in S3 or add a separate slice/owner so this finding is not left unplanned.

```
the pattern to copy. (Unknown columns still unchecked, folded into F-4's fix family.)
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:392**

- The verification block uses `cd backend && ...` for tests, whereas the repository guardrails require test/type-check/lint commands to be invoked through root `make` targets. Use the canonical root target (or add/document a supported focused target) so the reproduction instructions follow the project workflow.

```
cd backend && uv run pytest tests/unit/modules/ tests/unit/services/data_ingestion/ -q
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:226**

- `OK-ish` is not defined in the verdict legend above, so this row cannot be interpreted consistently. Because the same row documents a silent factor-resolution failure, choose one of the defined statuses (or add explicit criteria for a new status) rather than leaving an ad-hoc label.

```
| provider                       | within factors                     | plain `str`, same                                                                                                                                     | select, required ✅      | OK-ish (F-11)                                             |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:382**

- S4's scope says "whitespace-strip ... everywhere", but the shipped validators only reject whitespace-only values in some cases and do not uniformly strip accepted values (for example, process-emissions and purchase return the original non-blank string). Use "reject whitespace-only" unless normalization is actually part of the intended fix.

```
| **S4**     | Backend DTO consistency fixes: animal-RF validators (use ≥ 0, non-empty ids), whitespace-strip on required strings everywhere, digits-only `user_institutional_id` (if confirmed).                                                                                                                                                              | F-7 (DTO part), F-9, F-10 | ✅ merged in #2231 (v1.4.0)                                                                       |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:380**

- For reference CSVs, an invalid present numeric does not become a row error: `_to_float` raises from `_parse_building_rooms`, and `ReferenceDataCSVProvider.ingest` catches it as a job-level ERROR (reference_data.py:149-214). The S2 scope currently says both factor and reference failures are row errors; distinguish the two failure surfaces.

```
| **S2**     | Factor providers persist `validate_create`'s validated output; unparseable numerics = row error, not raw-string passthrough — in both `_convert_value` (factors) and `_to_float` (reference data, the F-2 residual).                                                                                                                            | F-2, F-3                  | ✅ merged in #2231 (v1.4.0)                                                                       |
```

**docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md:138**

- The matrix identifies P1b factor CSVs as having no unknown-column check, but this gap is absent from F-1…F-13 and the follow-up table. `base_factor_csv_provider` only checks missing headers in strict mode (lines 332-342), so a typo in a factor value column can still be ignored; please classify/assign this gap or explicitly document why factor headers are exempt.

```
| Unknown column / key                                           | ✅ hard error since #2216 (was warn-only → **F-1**, fixed)                                         | ⚠️ no check at all                                                                                                                                                         | ⚠️ silently dropped by `filtered_row` (`:1234-1239`); columns named `data` or `status` **survive** the filter (they are DTO fields) → **F-4** | ⚠️ swept into persisted `data` — verified on **all 15** Create DTOs → **F-5**                                                                                                                                   | ⚠️ no unknown-column check (`missing = expected - actual` only)       |
```

</details>

---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line null) — Copilot

Implementation-plan files are expected to include a `status` field in the frontmatter (per `docs/src/contributing/guardrails.md:27-28`). This new plan currently omits it, which can break consistency for auto-indexing/filters that rely on `status`.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 184) — Copilot

This matrix row still describes the pre-#2231 implementation: `_to_float` now raises for a present unparseable reference value, and the factor provider copies DTO-coerced fields back before persistence. Rebaseline the type-coercion cells instead of leaving F-2/F-3 marked as open here.

This issue also appears in the following locations of the same file:

- line 63
- line 235
- line 238

---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 435) — Copilot

The repository guardrails make root-level `make` targets canonical and specifically prohibit changing into a subdirectory for test commands. This verification snippet teaches the opposite; document a supported root-level targeted-test command or use the canonical test target.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 10) — Copilot

The front-matter summary says three ingestion paths, while the body and matrix explicitly audit four by adding P4 reduction-objective CSVs. Please make the scope count consistent; otherwise the document's stated coverage is ambiguous.

This issue also appears on line 271 of the same file.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 76) — Copilot

The "every required string field" claim is not true on the current HEAD: `PurchaseHandlerCreate.purchase_institutional_code` still only checks length, and `BuildingEmbodiedEnergyHandlerCreate.room_name` has no whitespace validator, so `'   '` is accepted. The regression test covers purchase `name` but omits both cases; narrow this claim or record the residuals in F-10/S4.

This issue also appears on line 246 of the same file.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 225) — Copilot

These frontend verdicts are the pre-#2231 snapshot. `headcount.ts` now marks `name`, `sius_code`, and both `fte` fields as required (with member FTE bounds), so the GAP-FE entries here no longer match the current code or the shipped S6 status. Update this table to retain only the remaining differences.

This issue also appears on line 320 of the same file.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 233) — Copilot

This row still describes the pre-#2231 behavior: `ProcessEmissionsHandlerCreate` rejects whitespace-only `category`, and `process_emissions.ts` now sets `subcategory.required: true`. Update the backend/frontend cells and verdict to match the current code.

This issue also appears on line 198 of the same file.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 362) — Copilot

The animal DTO no longer has "no validators": `ResearchFacilitiesAnimalHandlerCreate` currently validates numeric/non-negative `use` and non-empty required strings, with regression tests for `-5` and whitespace. Keep F-7 focused on any remaining permission asymmetry instead of reporting this shipped DTO fix as open.

This issue also appears on line 329 of the same file.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 188) — Copilot

After #2216, this P1a failure surface is historical rather than current: an unknown header is rejected before the delete/reinsert, so the job no longer reports success after inserting NULL surfaces for that typo. Mark this cell as the pre-fix behavior or replace it with the current failure surface.

This issue also appears on line 157 of the same file.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 295) — Copilot

This GAP-FE is stale: the current purchase config marks `coef_to_kg` required and sets `min: 0`, matching the backend validator. Update the row and keep any remaining open questions separate from the already-merged S6 fix.

This issue also appears on line 259 of the same file.
---

### File: `docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md` (Line 371) — Copilot

This part of F-9 is stale: the shared frontend required check now treats a whitespace-only string as empty via `v.trim() === ''`. Remove or mark that clause as resolved while keeping the still-open minimum, integer, and digits-only questions.
---

---

## Action Items

Triage date: 2026-08-25, verified against `dev` at `bf6d808a` (not the PR branch's
stale checkout). All items are doc accuracy — the PR is docs-only.

### Maintainability / refactoring

- [x] **docs/src/implementation-plans/1489-data-validation-audit-and-hardening.md** — sections A–C were the pre-#2216/#2231 snapshot and contradicted the doc's own "What is already fixed" list and the 2026-08-24 sweep addendum (8 Copilot comments: L63/184/235/238 `_to_float` + factor copy-back, L157/188 P1a failure surface, L198/233 process-emissions `category`/`subcategory`, L225/320 headcount config, L259/295 purchase `coef_to_kg`, L329/362 animal-RF DTO, L371 FE trim). Fix: rebaseline every affected row to the current state with the PR that fixed it (#2216, #2231, #2307), strike F-2/F-3/F-8/F-10 as fixed in section C, keep the pre-fix evidence in the finding text. Also fold in #2307 (merged after the sweep): RF `use`/`use_unit` required + per-unit bounds → F-8 closed, new D-8 (bounds undocumented).
- [x] **same file, frontmatter + L271** — summary says "three ingestion paths" while the body audits four (P4). Fix: say four, list reduction-objective CSVs.
- [x] **same file, L76** — _partial_: "whitespace-only is refused in every required string field" is wrong for `purchase_institutional_code` (length-only validator, `purchase/data_entries.py:82-89`) — that is N-1 and is now surfaced in the purchase table and F-10. The bot's second example (`BuildingEmbodiedEnergyHandlerCreate.room_name` unvalidated) is **wrong**: `c4bc9af2` (2026-08-20, in #2231) added the `building_name`/`room_name` whitespace validator (`buildings/data_entries.py:84-88`).
- [x] **same file, L435** — verification snippet used `cd backend && uv run pytest …`. Fix: `uv run --directory backend pytest …` (no cd, same targeted subset; `make test` has no single-directory form, noted inline).

### Dropped after verification

- **Suppressed comment, frontmatter L14** — "multi-line double-quoted `summary` breaks the generated index table": **wrong**. YAML folds line breaks inside a double-quoted scalar into spaces; `yaml.safe_load` of this frontmatter yields a summary with no `\n` (checked), so `gen_indexes.py` gets a single-line string.
- **Guilbert, "no mixing of French/English"** — human thread, already addressed in `7b08e594` (French section replaced by the English reading guide); left for the author to resolve.
