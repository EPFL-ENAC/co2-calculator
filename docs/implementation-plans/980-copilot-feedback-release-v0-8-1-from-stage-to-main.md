# Bot Review TODOs: PR #980

## Source Branch: `stage`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Copilot wasn't able to review this pull request because it exceeds the maximum number of lines (20,000). Try reducing the number of changed lines and requesting a review from Copilot again.

### Summary Feedback (github-advanced-security)

---

### Summary Feedback (github-advanced-security)

---

### File: `backend/app/services/data_ingestion/provider_factory.py` (Line 201) — github-advanced-security[bot]

## CodeQL / Commented-out code

This comment appears to contain commented-out code.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/601)

### File: `backend/tests/unit/services/test_year_config_service.py` (Line 115) — github-advanced-security[bot]

## CodeQL / Explicit returns mixed with implicit (fall through) returns

Mixing implicit and explicit returns may indicate an error, as implicit returns always return None.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/602)

### File: `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (Line 214) — github-advanced-security[bot]

## CodeQL / An assert statement has a side-effect

This 'assert' statement contains an [expression](1) which may have side effects.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/611)

### File: `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (Line 219) — github-advanced-security[bot]

## CodeQL / An assert statement has a side-effect

This 'assert' statement contains an [expression](1) which may have side effects.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/612)

### File: `backend/tests/unit/providers/test_unit_provider.py` (Line 291) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_u1 is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/608)

### File: `backend/tests/unit/providers/test_unit_provider.py` (Line 292) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_u2 is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/609)

### File: `backend/tests/unit/providers/test_unit_provider.py` (Line 301) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_u2 is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/610)

### File: `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (Line 261) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_user is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/603)

### File: `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (Line 318) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_cr is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/604)

### File: `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (Line 342) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_cr is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/605)

### File: `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (Line 366) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_user is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/606)

### File: `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (Line 394) — github-advanced-security[bot]

## CodeQL / Unused local variable

Variable \_cr is not used.

## [Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/607)

---

## Action Items

PR is BLOCKED for merge by GitHub's standalone `CodeQL` check (open code-scanning alerts), even though no branch protection is configured on `main`. So all alerts must be either fixed or dismissed.

### Critical: logic, security, correctness

- [ ] **backend/tests/unit/repositories/test_carbon_report_module_repo.py** (lines 214, 219) — `assert await repo.delete(...)` puts the actual call inside the `assert` expression. Under `python -O` asserts are stripped and the `delete` would never run. Fix: hoist into a temporary on each line, e.g. `result = await repo.delete(mod.id); assert result is True`. **Verdict: valid.**

### Maintainability / refactoring

- [ ] **backend/app/services/data_ingestion/provider_factory.py** (lines 200-201) — Two commented-out lines (`# if module_type_id is None: # return None`) just before `get_provider_by_keys` is called. Current code deliberately passes `module_type_id=None` through; the early-return was intentionally removed. Fix: delete the two comment lines. **Verdict: valid.**

### Dismiss as false-positive in GHAS UI (do not edit code)

- [ ] **`py/unused-local-variable` × 9** in `backend/tests/unit/providers/test_unit_provider.py` (lines 291, 292, 301) and `backend/tests/unit/repositories/test_carbon_report_module_repo.py` (lines 261, 318, 342, 366, 394). The codebase uses the `_var =` prefix as a deliberate convention to mark side-effect-only fixture calls (`cr = ...` when used; `_cr = ...` when only the DB side-effect matters) — this is the standard Python idiom that pylint/ruff/flake8 all respect. CodeQL is the outlier. **Verdict: wrong** (CodeQL contradicts an established convention). Action: dismiss alerts 603–610 with reason "won't fix / used by framework".
- [ ] **`py/explicit-return-in-function`** in `backend/tests/unit/services/test_year_config_service.py` (line 115). `_first_module_and_sub()` returns explicitly inside the loop but ends with `pytest.skip(...)` — which raises `Skipped`, so the fall-through path is unreachable. CodeQL doesn't model `pytest.skip` as a raising call. **Verdict: wrong** (false positive on flow analysis). Adding a dummy `return None` after a raising call is dead code — don't. Action: dismiss alert 602 with reason "false positive / pytest.skip raises".

### Notes

- **Copilot did not review this PR** — its summary says the diff exceeds the 20,000-line review limit. Every actionable signal here is from `github-advanced-security[bot]` (CodeQL).
- Final tally: 2 critical fixes, 1 maintenance fix, 10 dismiss-as-false-positive. (3 code edits across 2 files; 10 GHAS UI dismissals.)
