---
status: draft
issue: 1215
last_updated: 2026-05-22
title: "Move 'Incomplete' tag computation to backend"
summary: "Backend year-configuration response emits explicit incomplete + reasons per submodule/module. Frontend deletes its client-side derivation. Only factor + reference uploads are mandatory."
---

# 1215 — Move "Incomplete" tag computation to backend

## 1. Problem

**Symptom** (issue #1215): in the BackOffice → Configuration page, the
"Incomplete" tag remains visible on a module/submodule even when the
mandatory factor + reference uploads have completed successfully.

**Root cause**: the tag is derived client-side in
`frontend/src/stores/yearConfig.ts:460-503` by `isSubmoduleIncomplete()` /
`isModuleIncomplete()`. The derivation has several brittle checks that
conflate "missing job" with "errored job" and add non-mandatory data
sources into the rule. Concretely:

- Lines 465-468: `!sub.noFactors` branch returns `true` when
  `latest_factor_job.result !== 0` — i.e. an errored factor job is
  reported as Incomplete, even though "Incomplete" is supposed to mean
  *absence*, not run state. Errored jobs are already surfaced by the
  upload-card inline.
- Lines 469-478: the `mandatoryData` branch treats CSV `data` as
  mandatory whenever the flag is true. Per the strategic decision (see
  §2) `data` is not mandatory at all.
- Lines 480-482: same conflation for `latest_reference_job` — an
  errored job makes the submodule Incomplete.
- **Lines 484-487 (the likely smoking gun)**: a module-level
  `latest_common_data_job` is required to be present with
  `result === 0` for any submodule that is "common" (no
  `dataEntryTypeId`). When a module's common-data CSV doesn't exist or
  errored, this branch fires and the module-level
  `isModuleIncomplete()` returns true even when every per-submodule
  factor + reference upload is green — matching the screenshot in the
  issue body. Common-data is not part of the new mandatoriness rule
  either.

The fix is not another patch to this function — it is to **delete the
function** and let the backend, which owns the job state, emit the
flag.

## 2. Decision applied

**Move the source of truth to the backend.** Stop computing
`isSubmoduleIncomplete` / `isModuleIncomplete` in the frontend store.
The `/year-configuration/{year}` endpoint emits an explicit
`incomplete: bool` (plus rationale) per submodule and per module.
Frontend just renders the flag.

**Mandatoriness semantics** (confirmed): only `factor` and `reference`
uploads are mandatory. CSV `data` upload and `api_data` are NOT
mandatory and must NOT drive the "Incomplete" tag.

**Computation rule** (confirmed): a submodule is `incomplete` iff a
mandatory job is **missing** (no row in the database). A job that
exists but errored (`result == 2`) does NOT make the submodule
incomplete — the upload-card already surfaces the error inline.
"Incomplete" is about *absence*, not run state.

**Caveat**: a submodule that doesn't offer factors (`noFactors: true`
today) cannot be incomplete for missing factors. Same for reference
when the submodule has no reference target. See §7 open question (a)
on where this mandatoriness signal lives once we move the rule to the
backend.

Frontend `isSubmoduleIncomplete` / `isModuleIncomplete` derivations
get **deleted entirely** (no dual-path bloat — pre-v1.x; memory
"Backend is source of truth — frontend renders backend transforms").

## 3. Files to change

### Backend

- `backend/app/api/v1/year_configuration.py`
  - Lines 104-157: `_enrich_config_with_jobs` already injects
    `latest_*_job` fields. Either extend this function (or, preferred,
    add a sibling `_enrich_config_with_incomplete_flags`) to run after
    job enrichment and populate the new `incomplete` /
    `incomplete_reasons` fields on each submodule dict and on each
    module dict.
  - Single call site: the `GET /year-configuration/{year}` handler
    (further down in the same file — to be located precisely by the
    implementer; the file is 1006 lines). The handler currently calls
    `_enrich_config_with_jobs(config_dict, job_lookup)`; the new
    enrichment step is invoked here too.

- `backend/app/schemas/year_configuration.py`
  - Lines 345-374: `SubmoduleConfig` — add two typed fields:
    - `incomplete: bool = Field(default=False, ...)`
    - `incomplete_reasons: list[str] = Field(default_factory=list, ...)`
      (e.g. `["missing_factor", "missing_reference"]`).
  - Lines 385-395: `ModuleConfig` — add the same two typed fields at
    module level. While we're here, **also type the existing
    `latest_common_data_job` / `latest_common_factor_job` fields** —
    today the router writes them as untyped dict keys (see line 156),
    which is the inconsistency that lets the schema lie to the
    frontend about response shape. (Optional cleanup; flag in PR
    description if the implementer keeps it scope-creep-free.)

- Mandatoriness source — see §7 open question (a). Depending on the
  resolution, this may add either:
  - a new `backend/app/constants/submodule_mandatoriness.py` module
    (preferred — move the frontend constant verbatim), or
  - new typed fields on `SubmoduleConfig`
    (`mandatory_factor: bool`, `mandatory_reference: bool`,
    `has_factors: bool`, `has_data: bool`) populated from a table
    lookup.

### Frontend

- `frontend/src/stores/yearConfig.ts:460-503` — **DELETE**
  `isSubmoduleIncomplete()` and `isModuleIncomplete()`. Remove them
  from the store's return object at lines 582-583. Update
  `anyModuleIncomplete` (lines 522-527) to read backend `incomplete`
  flags from `config.value.config.modules[*].incomplete` instead of
  calling the deleted helpers.
- `frontend/src/components/organisms/data-management/ModuleConfig.vue:318-324`
  — change the `v-else-if="isModuleIncomplete(module)"` to read the
  backend field. Also drop the import at line 31.
- `frontend/src/components/molecules/data-management/SubmoduleItem.vue:140-149`
  — change `isSubmoduleIncomplete(submodule)` to read the backend
  field. Also drop the import at line 26.
- `frontend/src/components/organisms/data-management/ModuleConfig.vue:144-147`
  — the comment and guard reference `isModuleIncomplete`; update both
  to use the backend field.
- `frontend/src/composables/useModuleConfig.ts:39,176` — drop the
  destructure and the re-export of `isModuleIncomplete`.
- `frontend/src/composables/useSubmoduleConfig.ts:28,275` — same for
  `isSubmoduleIncomplete`.
- `frontend/src/types/` (and any OpenAPI-generated types if a codegen
  step exists — verify in `frontend/package.json` scripts) — surface
  the new `incomplete` / `incomplete_reasons` fields on submodule and
  module types.
- `frontend/src/constant/backoffice-module-config.ts` — depending on
  §7 (a), this file either shrinks (mandatoriness fields removed
  because backend now owns them) or stays put.

## 4. Approach

### 4.1 Backend: emit the flag

In `_enrich_config_with_incomplete_flags` (new helper in
`year_configuration.py`):

- For each submodule dict (already enriched with `latest_*_job`):
  - If the submodule's mandatoriness signal says factors are mandatory
    AND `latest_factor_job is None` AND
    `module.latest_common_factor_job is None` →
    `reasons.append("missing_factor")`.
  - If reference is mandatory AND `latest_reference_job is None` →
    `reasons.append("missing_reference")`.
  - `submodule["incomplete"] = bool(reasons)`.
  - `submodule["incomplete_reasons"] = reasons`.
- For each module dict, aggregate:
  - `module["incomplete"] = any(sub["incomplete"] for sub in
    enabled_submodules)` (only enabled — disabled submodules don't
    count, matching today's `isSubmoduleEnabled(sub) &&
    isSubmoduleIncomplete(sub)` in the deleted helper).
  - Module-level `incomplete_reasons` — see §7 (d).

Errored jobs (`result == 2`) do **not** count as incomplete (key
behavior change from the current frontend rule). The upload-card
surfaces error state independently.

### 4.2 Backend: regression + matrix tests

Add to `backend/tests/unit/services/test_year_config_service.py`
(or to a new helper-targeted file
`backend/tests/unit/v1/test_year_configuration_incomplete_flag.py`
since the logic currently lives in the router file — the implementer
picks based on where the helper ends up):

- **4-quadrant matrix** for a mandatory-factor + mandatory-reference
  submodule:
  - factor present + reference present → `incomplete is False`,
    `incomplete_reasons == []`.
  - factor present + reference missing → `incomplete is True`,
    reasons contains `"missing_reference"` only.
  - factor missing + reference present → `incomplete is True`,
    reasons contains `"missing_factor"` only.
  - factor missing + reference missing → `incomplete is True`,
    both reasons present.
- **Errored-job pin**: factor job exists with `result == 2`,
  reference job exists with `result == 0` → `incomplete is False`
  (errored ≠ missing). This is the regression invariant.
- **Disabled-submodule pin**: an enabled module with one disabled
  submodule that's missing factors → module-level `incomplete is
  False` (disabled subs don't count).
- **Module-level aggregation**: any enabled submodule incomplete →
  module incomplete.

### 4.3 Frontend: delete derivation, render backend flag

1. Delete `isSubmoduleIncomplete` and `isModuleIncomplete` from
   `yearConfig.ts` (lines 460-503). Remove from the return object
   (lines 582-583).
2. Update `anyModuleIncomplete` (lines 522-527) to read
   `config.value.config.modules[*].incomplete` instead of calling the
   deleted helpers. Keep `isReductionObjectiveIncomplete` as-is — that
   one is unrelated.
3. Update `ModuleConfig.vue:318` and `SubmoduleItem.vue:142` to read
   the backend flag (typed via the updated `ModuleConfig` /
   `SubmoduleConfig` types) — pulling from the enriched config dict
   the store already exposes.
4. Update `useModuleConfig.ts` (lines 39, 176) and
   `useSubmoduleConfig.ts` (lines 28, 275) — drop the destructured
   names and re-exports.
5. Regenerate TS types if `bun run codegen` (or equivalent) is the
   pattern — verify by checking `frontend/package.json`. Otherwise
   hand-edit `frontend/src/types/*` to add the new fields.

### 4.4 Frontend: extend integration test

In `frontend/tests/integration/data-management.spec.ts` (tests 9 and
9b around lines 472-631 today):

- Stub the year-config response with `incomplete: true` on a
  submodule → assert the badge renders.
- Stub with `incomplete: false` on a submodule whose `latest_factor_job`
  has `result == 2` (error) → assert NO badge renders. This is the
  **issue-#1215 regression case** translated to a unit-test contract:
  upload succeeded mandatorily, backend says not-incomplete, badge
  must hide.
- Delete any unit tests that targeted the now-removed helpers (none
  found in the search, but verify with `grep -r "isSubmoduleIncomplete"
  frontend/tests/`).

### 4.5 Manual smoke checklist

Run `make backend-dev` + `bun run dev`, navigate to
BackOffice → Configuration, and verify:

1. Mandatory factor + reference both successful → no "Incomplete" tag
   on submodule or module.
2. Mandatory factor missing → "Incomplete" tag visible; backend
   response includes `incomplete_reasons: ["missing_factor"]`.
3. Mandatory factor present but errored (`result == 2`), reference
   present and OK → **no** "Incomplete" tag (key behavior change vs
   current).
4. Data CSV errored or missing, all mandatories present → no
   "Incomplete" tag (data is not mandatory under the new rule).

## 5. Tests

### Backend

- 4-quadrant submodule matrix (see §4.2).
- Errored-job pin (regression; covers issue #1215 invariant at the
  unit level).
- Disabled-submodule pin.
- Module-level aggregation pin.
- File path: `backend/tests/unit/v1/test_year_configuration_incomplete_flag.py`
  (proposed — implementer co-locates with the helper's final home).

### Frontend

- Integration test asserting badge consumes the backend
  `incomplete` field directly (no client-side derivation).
- **Regression** for the issue body: stubbed response with all
  mandatory jobs `result == 0` and `incomplete: false` → no badge.
  Located in
  `frontend/tests/integration/data-management.spec.ts` alongside the
  existing tests 9 / 9b.

### Regression statement

The issue body scenario — mandatory factor + reference uploads
successful, "Incomplete" tag still visible — is covered by:
- the backend errored-job pin (proves the rule emits the right flag);
- the frontend integration test (proves the renderer consumes the flag
  and not a derived helper).

Both are mandatory per repo memory ("Bugs ship with regression
tests").

## 6. Verification

```bash
cd backend
uv run pytest tests/unit/v1/test_year_configuration_incomplete_flag.py -xvs
uv run pytest tests/integration/v1/ -k year_configuration -xvs

cd ../frontend
bun run lint && bun run typecheck
bun run test:integration
make type-check   # vue-tsc — husky-equivalent gate (memory note)

# Manual:
make backend-dev   # one terminal
bun run dev        # another terminal
# Navigate to Backoffice → Configuration and walk the 4 cases in §4.5.
```

## 7. Open questions

**(a) Where does the mandatoriness signal live once the rule moves to
the backend?**
Today `mandatoryReference` / `mandatoryData` / `noFactors` / `noData`
are hardcoded in `frontend/src/constant/backoffice-module-config.ts`.
The backend currently has no equivalent — so it cannot, today, know
whether a submodule's missing `latest_factor_job` is "incomplete" or
"this submodule doesn't have factors". Three options:

1. **Move the constant to backend verbatim** (preferred —
   single-source-of-truth, fits "Backend is source of truth"; lowest
   moving parts). Create
   `backend/app/constants/submodule_mandatoriness.py` keyed by
   `(module_type_id, data_entry_type_id)`. Surface the resolved flags
   on the `SubmoduleConfig` response so the frontend can keep showing
   per-submodule UI affordances (which still need to know e.g.
   `noFactors`).
2. Add per-submodule mandatoriness flags as typed `SubmoduleConfig`
   fields and populate from a DB-backed table (long-term clean; out
   of scope for a bug fix).
3. Compute mandatoriness from existing tables (e.g. "this
   `data_entry_type_id` has a row in `factor_types`") — fragile and
   requires the implementer to verify each module's data model.

**Recommendation: option 1 for this PR.** Defer 2/3 to a separate
issue.

**(b) Does the frontend `mandatoryReference` constant agree with what
the backend will read?**
Spot-check the constant (lines 38-70 today) — references are
mandatory for `train`, `plane`, `building`. Confirm during
implementation that the backend's resolved mandatoriness matches
every existing entry in `backoffice-module-config.ts` before deleting
the frontend copy.

**(c) Module-level aggregation when a module has
`latest_common_factor_job`.**
The existing frontend rule (line 466) treats
`mod.latest_common_factor_job` as a fallback when a submodule has no
`latest_factor_job`. Does the new backend rule honor this? Proposal:
*yes* — at module level, if the module exposes
`latest_common_factor_job` (i.e. it has a common-factor target), then
that job's presence/absence drives a module-level `incomplete` flag
in addition to per-submodule rollup. Verify by inspecting which
modules today populate `latest_common_factor_job` (the router at
`year_configuration.py:154-156`).

**(d) Module-level `incomplete_reasons`.**
Should the module-level response surface a reasons list (a flat union
of submodule reasons, or just a sentinel like `["submodule_incomplete"]`)?
The UI today only needs the badge — so the simpler `bool incomplete`
is enough for v1. Recommendation: ship `incomplete: bool` at module
level without `incomplete_reasons` for now; add per-module reasons
only if a future UX wants them.

**(e) Where does the new `_enrich_config_with_incomplete_flags` helper
live?**
Stay in `backend/app/api/v1/year_configuration.py` alongside
`_enrich_config_with_jobs` (router-co-located), or move to
`backend/app/services/year_config_service.py`? The existing
enrichment lives in the router file, which is unusual but consistent
with how this codebase has shaped it. Recommendation: keep
co-located in the router file for this PR; refactor both helpers to
the service in a follow-up if size becomes an issue (the router is
already 1006 lines).
