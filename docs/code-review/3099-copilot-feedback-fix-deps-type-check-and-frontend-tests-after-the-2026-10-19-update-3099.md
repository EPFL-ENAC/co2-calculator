# Bot Review TODOs: PR #3101

Source Branch: `fix/3099-deps-type-check-tests`
---

## Raw Feedback

### Summary Feedback (github-advanced-security)

---

### File: `backend/app/modules/equipment/data_entries.py` (Line 41) — github-advanced-security[bot]

## CodeQL / Statement has no effect

This statement has no effect.

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/1360)
---

### File: `backend/app/modules/equipment/data_entries.py` (Line 44) — github-advanced-security[bot]

## CodeQL / Statement has no effect

This statement has no effect.

[Show more details](https://github.com/EPFL-ENAC/co2-calculator/security/code-scanning/1361)
---

---

## Action Items

### Maintainability / refactoring

- [ ] **backend/app/modules/equipment/data_entries.py** (alerts 1360, 1361). CodeQL `py/ineffectual-statement` flags the `...` bodies of the two read-only property stubs under `if TYPE_CHECKING:`. Verdict: wrong. The `...` is the stub body that gives ty a read-only type; it never runs. The rule is severity `note`, tagged maintainability/useless-code, with no security severity. It is the same false positive maintainers already dismissed 12 times on the Protocol stubs in `app/schemas/data_entry.py` and `app/schemas/factor.py` (e.g. 508, 539, 540, 541, 569, 570). Fix: dismiss both alerts as "false positive"; no code change.
