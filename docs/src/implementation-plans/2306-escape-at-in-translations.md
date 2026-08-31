---
status: delivered
issue: 2306
last_updated: 2026-08-28
title: "Escape @ characters in i18n translation strings"
summary: "vue-i18n treats a raw @ as linked-message syntax, which compiles fine in dev but throws at render time in production; some translations also had it wrapped in smart-quoted {'@'} from a word processor. Escapes every @ as straight-quoted {'@'} and adds a regression test scanning all i18n files for unescaped @."
---

# Escape @ in translations (#2306)

## Problem

`gh issue view 2306` resolves to a pull request, not a standalone issue —
#2306 is the PR number, and it closed issue **#2305**, "[TEST]: @ character
in translations": adding a plain `@` to a translation string threw an error.
vue-i18n treats a raw `@` in a message as linked-message syntax; this
compiles in dev but throws a `SyntaxError` at render time in production
builds. A few existing translations also had `@` wrapped in smart-quoted
`{'@'}` (curly quotes, likely pasted from a word processor), which fails
compilation the same way.

## What shipped

PR #2306, "fix(i18n): escape @ in translations and add test", merged
2026-08-24 (`2611b061c`).

- `frontend/src/i18n/equipment.ts` — the EN and FR contact-email strings
  `co2calculator@epfl.ch` → `co2calculator{'@'}epfl.ch`.
- `frontend/src/i18n/tooltips.ts` — `planner-grant-section-title` (EN) had a
  smart-quoted `{'@'}` replaced with the correctly straight-quoted one.
- `frontend/tests/unit/i18n-at-escape.spec.ts` (new) — a `findUnescapedAt()`
  helper scans every `.ts` file under `frontend/src/i18n/` and flags any `@`
  that isn't part of an exact `{'@'}` sequence; asserts zero unescaped `@`
  across all real i18n files, so a future PR can't reintroduce this.

No follow-up issues filed.
