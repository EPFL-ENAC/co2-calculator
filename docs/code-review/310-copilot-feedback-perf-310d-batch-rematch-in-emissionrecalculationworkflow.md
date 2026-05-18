# Bot Review TODOs: PR #1027

## Source Branch: `perf/310d-batch-rematch-recalc`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR optimizes `EmissionRecalculationWorkflow.recalculate_for_data_entry_type` by replacing per-entry factor resolution DB calls with a single bulk factor fetch and an in-memory lookup keyed by `(kind, subkind)`, keeping the existing per-entry resolver as a fallback. This targets the recalculation hot path (not ingestion) and adds unit coverage to ensure the bulk fetch happens once and fallback resolution is only used on lookup misses.

**Changes:**

- Bulk-fetch factors once per `(data_entry_type_id, year)` and use a dict lookup to resolve `primary_factor_id` during emission recalculation.
- Keep the existing per-entry `ModuleHandlerService.resolve_primary_factor_id` path as a fallback for dict misses.
- Update unit tests to mock the new FactorRepository dependency and add a new test asserting single bulk fetch + fallback-on-miss behavior.

### Reviewed changes

Copilot reviewed 2 out of 2 changed files in this pull request and generated 2 comments.

| File                                                        | Description                                                                                                                           |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| backend/app/workflows/emission_recalculation.py             | Adds bulk factor prefetch + dict-based rematch, with fallback to existing per-entry resolver and a new `_lookup_factor_id` helper.    |
| backend/tests/unit/workflows/test_emission_recalculation.py | Updates existing tests to mock FactorRepository and adds a new unit test asserting the single bulk fetch behavior and fallback usage. |

---

### File: `backend/app/workflows/emission_recalculation.py` (Line 95) — Copilot

## The bulk factor prefetch runs whenever handler.kind_field is set, even if no entries will ever satisfy the per-entry `should_refresh` gate (e.g. Strategy B handlers where `kind_field` is derived and not present in `entry.data`). That introduces an extra DB SELECT per recalc slice that previously did zero factor lookups. Consider gating the prefetch on whether at least one entry has `kind_field` present (or computing `should_refresh` first) so Strategy B slices skip the bulk fetch entirely.

### File: `backend/app/workflows/emission_recalculation.py` (Line 151) — Copilot

## Inside the `if should_refresh:` block, `handler.kind_field` is still typed as `Optional[str]` (because the `is not None` check happens when computing `should_refresh`), but `_lookup_factor_id` requires `kind_field: str`. This is likely to fail mypy type checking. Consider restructuring the condition to check `handler.kind_field is not None` directly in the `if` statement (or assign to a local non-optional `kind_field` variable / add an `assert handler.kind_field is not None`) before calling `_lookup_factor_id`.

---

## Action Items

### Critical: logic, security, correctness

- [ ] **backend/app/workflows/emission_recalculation.py** (line ~146-151): `handler.kind_field` is typed `Optional[str]` at the `_lookup_factor_id` call site (the `is not None` check is hidden inside `should_refresh`), but `_lookup_factor_id` requires `kind_field: str`. Likely mypy failure. Narrow the type by checking `handler.kind_field is not None` directly in the `if` (or bind to a local non-Optional variable, or add an `assert`).

### Performance

- [ ] **backend/app/workflows/emission_recalculation.py** (line ~89-110): The bulk factor prefetch fires whenever `handler.kind_field is not None`, even for Strategy B handlers (e.g. professional_travel/plane) where `kind_field` is derived in `pre_compute` and never appears in `entry.data`. For those slices the prefetch adds a wasted SELECT and zero entries will pass `should_refresh`. Gate the prefetch on at least one entry having `kind_field` present (e.g. compute `should_refresh` candidates first, or `any(handler.kind_field in e.data for e in entries)`) so Strategy B slices skip the bulk fetch.
