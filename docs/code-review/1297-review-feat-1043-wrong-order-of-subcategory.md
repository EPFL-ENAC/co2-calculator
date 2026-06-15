# PR #1297 — Code Review (max effort)

**PR**: `feat/1043 wrong order of subcategory` by @BenBotros
**Branch**: `feat/1043-wrong-order-of-subcategory` (rebased onto `origin/dev` `a71351cb` + force-pushed)
**Scope**: 4 files, +204/-171 — fixes issue #1043 (Purchase/Equipment boxplot subcategory order)
**CI after rebase**: `Backend Lint/Type Check` and `Backend Tests` both red — **but** failure is in the `Install uv` step (CI flake from `astral-sh/setup-uv@v4`); code-level `make lint`, `make type-check`, and `mypy app/` all pass locally. **Rerun CI to get a real signal.**

## Verdict: SPLIT — sort fix OK to ship; bundled label-enrichment feature needs work

Issue #1043 is specifically about **subcategory order** ("the display of the subcategories are not in the right order"). The PR delivers that fix correctly on the frontend (sort-by-value-desc + top-3 + rest, applied to both Purchase and Equipment).

However, the author bundled a SECONDARY improvement — replacing raw UNSPSC codes with i18n `translation_key` labels for Purchase — that is **non-functional in production** as written (F1, verified). This bundled label feature also misses Equipment (F2) and has correctness issues (F3, year filter).

**Recommendation**: Either (a) merge the sort fix and split the label-enrichment into a follow-up PR where the data path can be completed properly, or (b) ask the author to address F1+F2+F3 in this PR before merge. Option (a) ships the actual #1043 fix today; option (b) keeps the bundled scope but delays.

## P0 — Bug-level (must fix before merge)

### F1. The label enrichment is a no-op for current production data (bundled feature, not #1043)

**Scope note**: This is about the SECONDARY label-improvement the author bundled into the PR, not the primary sort fix. The primary sort fix is correct and ships.

**Evidence (verified)**:

- Checked **all 21** purchase seed CSVs in `backend/seed_data/purchases*.csv`: **none** contain a `translation_key` column. Headers vary by file but the column is absent everywhere.
- `PurchaseCommonFactorHandler.value_fields` (`app/modules/purchase/schemas.py:441`) declares `translation_key`, but CSV ingestion only writes fields present in the row.
- Grepped the entire backend: **no Python code writes** `Factor.values['translation_key']` anywhere — only reads (the new `enrich_breakdown_with_factor_labels` and `module_handler_service.py:170,208`).
- `module_handler_service.py:170,208` reads via `values.get("translation_key") or kind_value` — meaning the project already knows the field is often absent and has documented fallback semantics for taxonomy.

**Consequence**: `enrich_breakdown_with_factor_labels` queries Factor rows, filters with `if row.code and row.label` (rejects NULL/empty `translation_key`), produces an empty `code_to_label` map, attaches nothing. The frontend `EmissionTypeBreakdownChart.vue:224` falls through to `child.name` which is the raw UNSPSC code. Chart legend shows `'10121700'` instead of `'Fish food'`.

**Fix**: Either (a) extend the seed CSVs to include `translation_key`, (b) populate `Factor.values['translation_key']` via a separate seeding step, or (c) thread label resolution through `DataEntry`/i18n catalog rather than `Factor.values`. Or split the label improvement out of this PR entirely (recommended path — ship the actual #1043 sort fix, do labels properly in a follow-up).

**Severity for the bundled label feature**: P0. **Severity for issue #1043**: not applicable (sort fix works independently).

---

### F2. Equipment branch silently lacks enrichment — contradicts #1043 acceptance criteria

**Evidence**: `backend/app/api/v1/carbon_report_module.py` — `_MODULE_TOP_CLASS_LABEL_FIELD` is registered ONLY for `ModuleTypeEnum.purchase`. Equipment uses `group_by_field='equipment_class'`, whose values in `equipments_factors.csv` are raw free-form English strings (`'Power supplies'`, `'AFM microscopes'`, `'3D printer'`).

**Consequence**: A French-locale user viewing `equipment` top-class breakdown sees segments labelled in English (`'Power supplies'` etc.) because `te('Power supplies')` returns false. Issue #1043 explicitly states the fix must apply to **both Purchase AND Equipment** — only the sort half does.

**Fix**: Either register Equipment in `_MODULE_TOP_CLASS_LABEL_FIELD` with the right `factor_label_field`, OR explicitly document that Equipment labels are already canonical and the sort-only fix is intentional.

**Severity**: P0 — direct acceptance-criteria miss.

---

### F3. Missing `Factor.year` filter — non-deterministic labels across years

**Evidence**: `backend/app/services/data_entry_emission_service.py:822` — the enrich SELECT filters by `Factor.data_entry_type_id` and `Factor.classification[group_by_field].in_(codes)` but **not by `Factor.year`**. Factor identity is `(data_entry_type, year, classification, emission_type)`. `.distinct()` over `(code, label)` returns multiple rows when the same code exists across years with diverged translation_keys; `code_to_label[row.code] = row.label` is last-write-wins by DB iteration order.

**Consequence**: A code whose `translation_key` was updated between years (e.g. `purchase_factor_fish_food` → `purchase_factor_fish_feed`) will render with whichever label PG returns last — non-deterministic across requests, may differ between a 2023 report and 2024 report.

**Fix**: Thread `report_year` from the endpoint to `enrich_breakdown_with_factor_labels` and add `Factor.year == report_year` to the WHERE clause. (The parent endpoint already passes `report_year=int(year)` to `get_top_class_breakdown`; the helper is the only year-blind step in the chain.)

**Severity**: P0 — correctness defect that activates the moment F1 is fixed (label data starts existing).

## P1 — Code-quality / architecture (should fix before merge)

### F4. NaN propagation in `rankSubkeys`

**Evidence**: `ModuleCarbonFootprintChart.vue:629-631` — `Number(row?.[k] ?? 0)` returns `NaN` when `row[k]` is a non-numeric string. The subsequent `(b.value - a.value)` comparator returns `NaN`, which JS sort treats engine-dependently (V8 treats as 0; spec-compliant TimSort may differ).

**Consequence**: A subcategory with a non-numeric value (e.g. `''` or unexpected type) lands arbitrarily in the top-3 — wrong "top emitter" displayed and the legitimate top emitter demoted to `purch_rest`.

**Fix**: Coerce explicitly: `const v = Number(row?.[k]); return Number.isFinite(v) ? v : 0`.

### F5. NaN poisons `purchRestValue` reduce

**Evidence**: `ModuleCarbonFootprintChart.vue:638` — `.reduce((s, e) => s + e.value, 0)` becomes `NaN` if any `e.value` is `NaN`. ECharts then drops the segment with no error surfaced — **violates project rule "no silent fallbacks"**.

**Fix**: Filter or coerce values before reducing, OR coerce inside reduce: `s + (Number.isFinite(e.value) ? e.value : 0)`.

### F6. Silent fallback in label filter — `if row.code and row.label`

**Evidence**: `data_entry_emission_service.py:836-837` — truthy filter on `row.label` drops rows whose translation_key is the empty string. Per project memory `feedback_no_silent_fallbacks.md`, missing data should surface, not be swallowed.

**Fix**: Either log/raise when an expected label is absent, or restrict the filter to `if row.code is not None`.

### F7. Inconsistent dict access — raw `child["name"]` vs defensive `child.get("name")`

**Evidence**: `data_entry_emission_service.py:814` uses `child["name"]` in a set comprehension; line 817 uses `child.get("name") != "rest"`. Asymmetric — a malformed child dict will `KeyError` at line 814 while the surrounding code expects degradation.

**Fix**: Pick one. Either both raise or both use `.get()`.

### F8. `ModuleCarbonFootprintChart.vue` is 1538 lines after this PR — pre-existing limit violation, this PR widens it

**Evidence**: Per project memory `feedback_vue_component_500_line_limit.md`: hard limit ≤500 lines, refactor at 400. The file **already exceeded the limit pre-PR** (was likely ~1413 lines). This PR adds ~125 net lines — does not create the violation, but does miss an opportunity to extract a composable while rewriting a large chunk.

**Recommendation (not a blocker for this PR)**: When this file next gets a substantial change, extract `buildStackedSeries(categoryKey, subkeys, labels, palette)` into a composable. The PR's own equipment/purchases rewrite proves the pattern is extractable. Flag the file as technical debt regardless of this PR's merge decision.

### F9. Two parallel sort-with-rest-last implementations

**Evidence**: `EmissionTypeBreakdownChart.vue:214-218` and `ModuleCarbonFootprintChart.vue:625-631` both implement `(a.name==='rest')?1 : (b.name==='rest')?-1 : b.value-a.value`. Backend `it_breakdown.py:254` (`build_it_breakdown`) already has the canonical Python equivalent `lambda x: (x['name']=='rest', -x['value'])`.

**Fix**: Sort once at the data layer (backend pre-sorts, frontend dumb-iterates — the `ItFocusSection` pattern), or extract a shared `sortTopClassChildren()` composable. The string `'rest'` should be a single exported constant.

### F10. `EQUIPMENT_SUBKEYS` / `PURCHASES_SUBKEYS` duplicate `CATEGORY_CHART_KEYS`

**Evidence**: `ModuleCarbonFootprintChart.vue:609` hardcodes the lists; `composables/useEmissionTreemap.ts:61-79` already exports them as `CATEGORY_CHART_KEYS.equipment` / `.purchases` (which mirrors backend `CATEGORY_CHART_KEYS` in `emission_breakdown.py`).

**Fix**: Import from the composable. Three-way sync becomes one-way.

## P2 — Quality concerns

### F11. `enrich_breakdown_with_factor_labels` — mutate-and-return ambiguity

The function mutates input dicts in place AND returns the list. Caller `carbon_report_module.py:443` rebinds the result, but the input is silently modified. Pick one semantic; mutation is dangerous if the breakdown is ever cached or fanned out to multiple consumers. Also: function is 47 lines, violates project's ≤40-line backend function limit.

### F12. `enrichedDatasetSource` asymmetric copy semantics

Returns shallow `{...row}` clones for `equipment` / `purchases` branches but returns the original `row` reference unchanged for other categories. Latent reactivity hazard.

### F13. `segmentLabelOverrides` module-level Map shared across instances

`EmissionTypeBreakdownChart.vue:157` declares the Map at module scope, mutates it via `.clear()` + `.set()` inside a `computed`. Pre-existing pattern this PR widens. Two simultaneous component instances (print mode, multi-module views) can read each other's labels.

### F14. Producer/consumer contract on `translation_key` is undocumented

Consumer first tries `SUBCATEGORY_LABEL_MAP[override]`, then falls through to `te(override) ? t(override) : override`. No schema enforces what shape backend should write — `'purchase_factor_fish_food'` vs `'charts-scientific-subcategory'` would both "work" through different branches. Fragile to future producer changes.

### F15. Architectural altitude — should extend existing `label_field` path

`get_top_class_breakdown` (`data_entry_emission_repo.py:786`) already accepts `label_field` and emits `MAX(label)` per group inside the same ranked CTE. The new path adds a second SQL roundtrip when the existing mechanism could carry the label in one query. Right altitude: extend `label_field` to accept a `label_source` qualifier (`'data_entry' | 'factor'`).

## Karpathy checklist mapping

| Question                                              | Answer                                                                                                                                                  |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Code satisfies the original requirements?             | **Partial.** Sort-by-value-desc + top-3 + rest: yes. Human-readable labels: no (F1, F2).                                                                |
| Edge cases / error handling / invalid inputs covered? | **No.** NaN propagation (F4, F5), empty-string label (F6), `KeyError` risk (F7).                                                                        |
| APIs / imports / framework calls real and valid?      | Yes.                                                                                                                                                    |
| Auth / authorization / validation / security correct? | N/A for this PR's scope.                                                                                                                                |
| Code simpler than necessary, or overengineered?       | **Overengineered.** 1538-line component (F8), duplicated constants (F10), dual-encoding dataset rows.                                                   |
| Duplicated or dead code introduced?                   | **Yes.** Two sort impls (F9), 11 dead dataset dimensions, two label-resolution paths (F15).                                                             |
| Naming / typing / comments accurate?                  | **Partial.** `_MODULE_TOP_CLASS_LABEL_FIELD` name suggests generality; only Purchase is registered (F2).                                                |
| Performance / concurrency / scalability problems?     | **Yes.** Missing year filter (F3), no index on JSON extract, second DB roundtrip per request (F15).                                                     |
| Tests for happy path / edge cases / failure?          | **No tests added.** Author's own checkbox unchecked.                                                                                                    |
| Would I approve this if a junior wrote it?            | **No.** Ask for: F1 (seed translation_key), F2 (equipment coverage decision), F3 (year filter), F4/F5 (NaN guards), F8 (extract composable), and tests. |

## Recommended action

**Two paths, pick one:**

**Path A — ship the actual #1043 fix today, defer the bundled label feature**:

1. Ask author to revert the backend changes (`carbon_report_module.py`, `data_entry_emission_service.py`) and the `EmissionTypeBreakdownChart.vue:224` change that consumes `translation_key`.
2. Keep the frontend sort fix in `ModuleCarbonFootprintChart.vue` and `EmissionTypeBreakdownChart.vue:214-218` (the actual #1043 fix).
3. Address F4 + F5 (NaN guards) before merge.
4. F8/F10 noted as tech debt, not blocking.
5. Open a follow-up issue/PR for the label enrichment with a proper data-path plan.

**Path B — finish the bundled scope in this PR**:

1. Address F1 (populate `translation_key` data) — likely requires updating seed CSVs and possibly the ingestion code.
2. Address F2 (Equipment coverage) — either register in `_MODULE_TOP_CLASS_LABEL_FIELD` or document why Equipment is intentionally sort-only.
3. Address F3 (year filter).
4. Address F4 + F5 (NaN guards).
5. F6–F10 negotiable.

**Either path: rerun CI** — current failures are infra (`Install uv` step), not code.

Path A is recommended: it ships the actual issue #1043 fix today and gives the label feature room to be done properly. Path B is honorable if the author wants to keep the bundled scope.

## Findings JSON (machine-readable)

```json
[
  {
    "file": "backend/app/services/data_entry_emission_service.py",
    "line": 825,
    "summary": "Producer never produces labels — seed CSV has no translation_key column, so enrichment returns empty for production data and frontend falls back to raw UNSPSC codes",
    "failure_scenario": "After shipped seed_factors runs, Factor.values['translation_key'] is NULL for all rows. The `if row.code and row.label` filter drops everything, code_to_label is empty, frontend renders '10121700' instead of 'Fish food'."
  },
  {
    "file": "backend/app/api/v1/carbon_report_module.py",
    "line": 382,
    "summary": "Equipment branch lacks label enrichment despite #1043 requiring fix in both Purchase AND Equipment",
    "failure_scenario": "fr-CH user opens equipment top-class breakdown; backend returns name='Power supplies' (no translation_key), frontend te() returns false, French UI shows English source string."
  },
  {
    "file": "backend/app/services/data_entry_emission_service.py",
    "line": 822,
    "summary": "Missing Factor.year filter in enrich query — non-deterministic translation_key resolution across years",
    "failure_scenario": "Code with diverged translation_keys across years (renamed between 2023 and 2024) renders with whichever PG returns last; can flip request-to-request."
  },
  {
    "file": "frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue",
    "line": 630,
    "summary": "NaN propagation in rankSubkeys via Number(row?.[k] ?? 0) when row[k] is non-numeric",
    "failure_scenario": "Subcategory row contains non-numeric value → NaN → sort comparator returns NaN → V8 treats as 0, items placed arbitrarily; wrong subcategory shown as top emitter."
  },
  {
    "file": "frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue",
    "line": 638,
    "summary": "NaN poisons reduce accumulator for purchRestValue — segment vanishes silently (violates 'no silent fallbacks' rule)",
    "failure_scenario": "Any e.value=NaN → purchRestValue=NaN → ECharts drops the segment, total stack visibly shrinks, no console error."
  },
  {
    "file": "backend/app/services/data_entry_emission_service.py",
    "line": 837,
    "summary": "Silent fallback — truthy filter drops empty-string labels with no signal",
    "failure_scenario": "Factor.values['translation_key']='' → row silently filtered → frontend renders raw code, bug invisible in monitoring."
  },
  {
    "file": "backend/app/services/data_entry_emission_service.py",
    "line": 814,
    "summary": "Inconsistent dict access — raw child['name'] vs surrounding child.get('name')",
    "failure_scenario": "Upstream breakdown payload regression / partial child dict missing 'name' → KeyError raised inside enrich step → /top-class-breakdown returns 500 instead of degrading gracefully."
  },
  {
    "file": "frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue",
    "line": 1,
    "summary": "File is 1538 lines after this PR — over 3× the 500-line hard limit (project rule)",
    "failure_scenario": "Project memory violation. The chart-series builder pattern (lines ~770-1200) is the obvious composable to extract; this PR proves the equipment/purchases pattern is extractable and could net-reduce the file."
  },
  {
    "file": "frontend/src/components/charts/results/EmissionTypeBreakdownChart.vue",
    "line": 214,
    "summary": "Two independent sort-by-value-with-rest-last implementations (this file + ModuleCarbonFootprintChart.vue + backend it_breakdown.py)",
    "failure_scenario": "When the rest sentinel changes, every consumer breaks independently. Right fix: sort once at the data layer or share a composable."
  },
  {
    "file": "frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue",
    "line": 609,
    "summary": "EQUIPMENT_SUBKEYS / PURCHASES_SUBKEYS duplicate CATEGORY_CHART_KEYS already in composables/useEmissionTreemap.ts:65-76",
    "failure_scenario": "Adding a new purchases subcategory requires updating three lists (backend CATEGORY_CHART_KEYS, frontend useEmissionTreemap, this file); silent divergence between treemap and bar chart."
  },
  {
    "file": "backend/app/services/data_entry_emission_service.py",
    "line": 798,
    "summary": "enrich_breakdown_with_factor_labels mutates input AND returns it; also 47 lines (> 40-line backend function limit)",
    "failure_scenario": "Mutation-and-return ambiguity is unsafe under caching/fan-out. Function mixes three concerns: collect codes, build/run query, attach labels."
  },
  {
    "file": "frontend/src/components/charts/results/ModuleCarbonFootprintChart.vue",
    "line": 668,
    "summary": "enrichedDatasetSource asymmetric copy semantics — {...row} for equipment/purchases, original ref for others",
    "failure_scenario": "Future downstream mutation on a non-equipment row aliases back into datasetSource.value, breaks the wrapper's invariant; latent reactivity loop."
  },
  {
    "file": "frontend/src/components/charts/results/EmissionTypeBreakdownChart.vue",
    "line": 157,
    "summary": "Module-level mutable segmentLabelOverrides Map shared across all component instances",
    "failure_scenario": "Two simultaneous component instances (print mode, multi-module views) interleave .clear() + .set() calls; translateSubcategory reads the other instance's labels."
  },
  {
    "file": "frontend/src/components/charts/results/EmissionTypeBreakdownChart.vue",
    "line": 224,
    "summary": "Producer/consumer contract on translation_key undocumented — fragile to future producer changes",
    "failure_scenario": "Future backend change populates Factor.values['translation_key'] with a UI-namespaced key; rendering works through wrong branch by accident, until SUBCATEGORY_LABEL_MAP grows a collision."
  },
  {
    "file": "backend/app/services/data_entry_emission_service.py",
    "line": 800,
    "summary": "Wrong altitude — should extend existing label_field path instead of adding parallel mechanism",
    "failure_scenario": "get_top_class_breakdown's label_field already does MAX(label) per group inside the same CTE. The new path adds a second DB roundtrip per request and a parallel mechanism that future modules will have to choose between."
  }
]
```
