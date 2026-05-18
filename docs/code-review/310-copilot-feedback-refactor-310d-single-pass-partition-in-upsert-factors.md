# Bot Review TODOs: PR #1019

## Source Branch: `refactor/310d-upsert-factors-single-pass`

## Raw Feedback

### Summary Feedback (copilot-pull-request-reviewer)

## Pull request overview

This PR refactors `FactorRepository.upsert_factors` to partition input factors into “year-scoped” vs “non-year-scoped” subsets using a single pass, aligning with Plan 310-D’s goal of removing redundant iteration while preserving existing upsert behavior.

**Changes:**

- Replace two list comprehensions over `factors` with a single `for` loop that appends into `with_year` and `no_year`.
- Keep partition ordering and downstream `_upsert_subset(..., year_present=...)` call behavior unchanged.

---

## Action Items

_No substantive items — Copilot's summary describes the refactor without flagging any issues; no inline comments were left._
