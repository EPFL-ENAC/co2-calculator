# Bot Review TODOs: PR #1387

## Source Branch: `fix/862/correct-permissions-scope`

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This pull request fixes backoffice reporting scoping by treating the metier “affiliation” scope token as an ACCRED unit **cf** (`institutional_id`) and resolving it to a **unit subtree** via `path_institutional_code`, then enforcing an **intersection clamp** so scoped callers can never query outside their subtree.

**Changes:**

- Replace prior `path_name`/LVL3 affiliation logic with cf→institutional_code→descendant-subtree resolution and apply `scope_set ∩ filter_set` across backoffice reporting queries.
- Thread `(is_global, scope_cfs)` through reporting repository methods and route handlers; remove the old list-narrowing approach.
- Add/refresh unit + integration tests to cover fixture coherence, resolver behavior, and end-to-end scoping over real DB queries.

**Review notes (blocking):**

- `backend/app/utils/scoping.py` builds LIKE patterns with `func.concat(...)`. On SQLite (used by the new E2E tests in this PR), `concat()` is typically not available and can fail at runtime (“no such function: concat”). This should be rewritten using SQLAlchemy string concatenation (`+`) or SQLAlchemy’s `concat` expression helper to remain cross-dialect.

### Reviewed changes

Copilot reviewed 13 out of 13 changed files in this pull request and generated no comments.

<details>
<summary>Show a summary per file</summary>

| File                                                                              | Description                                                                                                       |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| docs/src/implementation-plans/862-backoffice-affiliation-scope-by-unit-subtree.md | Adds delivered implementation plan documenting cf→subtree resolution and intersection invariant.                  |
| docs/src/backend/06-PERMISSION-SYSTEM.md                                          | Updates permission-system docs to describe the new subtree-scoped backoffice.reporting model.                     |
| backend/app/utils/scoping.py                                                      | Replaces `path_name` affiliation predicate with `build_scope_subtree_predicate` (EXISTS over code-subtree match). |
| backend/app/repositories/carbon_report_module_repo.py                             | Adds scope cf→subtree resolver and applies scope/filter intersection clamp across report queries.                 |
| backend/app/providers/role_provider.py                                            | Makes backoffice_metier affiliation token equal to ACCRED unit cf; removes sortpath/LVL3 extraction logic.        |
| backend/app/api/v1/backoffice.py                                                  | Threads scope into reporting overview/exports; switches year query narrowing to subtree predicate.                |
| backend/app/api/v1/backoffice_reporting.py                                        | Applies subtree predicate to `/backoffice-reporting/{units,affiliations}` listing queries.                        |
| backend/app/providers/test_fixtures.py                                            | Rebuilds TEST units into a coherent ENAC subtree and sets `TEST_AFFILIATION` to the anchor cf.                    |
| backend/tests/unit/utils/test_scoping.py                                          | Adds unit tests for the SQL-level subtree predicate composition.                                                  |
| backend/tests/unit/repositories/test_carbon_report_module_repo.py                 | Adds unit tests for scope resolver + intersection invariant + scoped overview clamp.                              |
| backend/tests/unit/providers/test_test_fixtures.py                                | Adds coherence tests ensuring TEST fixtures exercise a real scope subtree.                                        |
| backend/tests/unit/providers/test_role_provider.py                                | Updates role-provider tests to assert metier scope is cf-based (no sortpath parsing).                             |
| backend/tests/integration/v1/test_permission_scope_e2e.py                         | Replaces SQL-string-emulation mocks with real in-memory DB E2E coverage for backoffice scoping.                   |

</details>

---

### File: `backend/tests/unit/utils/test_scoping.py` (Line 47) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable anchor is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/677)

### File: `backend/tests/unit/utils/test_scoping.py` (Line 47) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable child is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/678)

### File: `backend/tests/unit/utils/test_scoping.py` (Line 47) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable leaf is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/679)

### File: `backend/tests/unit/utils/test_scoping.py` (Line 47) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable outside is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/680)

## Action Items

### Maintainability / refactoring

- [ ] **backend/app/utils/scoping.py** — `build_scope_subtree_predicate` builds LIKE patterns with `func.concat(...)`, which renders a literal `concat()` call rather than the SQL-standard `||`. Fix: replace each `func.concat(a, b)` with string concatenation via the `+` operator (e.g. `col(anchor.institutional_code) + " %"`), which SQLAlchemy renders as `||` on both SQLite and Postgres. Bot got it wrong that this _currently_ fails — verified the test SQLite is 3.50.4 (has `concat()` since 3.44) and all E2E tests pass; this is a portability hardening, not a live bug.
- [ ] **backend/tests/unit/utils/test_scoping.py** (line 47) — `test_matches_anchor_and_descendants_only` unpacks `anchor, child, leaf, outside` from `_enac_subtree(...)` but never references them (it asserts on query results), tripping four CodeQL unused-variable alerts. Fix: drop the unpacking — call `await _enac_subtree(db_session, make_unit)` without assignment (matching the sibling test at line 55).
