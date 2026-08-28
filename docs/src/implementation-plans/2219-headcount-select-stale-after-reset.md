---
status: delivered
issue: 2219
last_updated: 2026-08-28
title: "Fix headcount select going stale after a form reset"
summary: "Standard users could only create one train/plane entry before needing to refresh the page. The shared headcount-member select in the travel-like dynamic form was keyed only on headcountMemberCount, so form.reset() after a successful submit didn't remount it, leaving it in stale state that blocked the next submission."
---

# Headcount select stale after reset (#2219)

## Problem

A standard user could add one travel entry (e.g. train or plane), but a
second one silently failed to create — the page had to be reloaded before
another entry could be added.

## Root cause

The bug wasn't specific to trains/planes: it was in the shared
headcount-member `q-select` used by the generic travel-like dynamic form.
That select was keyed only on `headcountMemberCount`, so calling the form's
`reset()` after a successful submission didn't force Vue to remount it. The
select was left holding stale internal state, which blocked further
submissions until a full page reload reset it.

## What shipped

PR #2333, "fix: force re-render of headcount select on reset (#2219)",
merged 2026-08-25 (`6bac075da`).

`frontend/src/components/organisms/module/ModuleForm.vue` (+3/-1):

- `ModuleForm.vue:667` — new `const headcountSelectKey = ref(0)`.
- `ModuleForm.vue:155` — the select's `:key` binding becomes
  `` `${headcountMemberCount}-${headcountSelectKey}` `` instead of
  `headcountMemberCount` alone.
- `ModuleForm.vue:1275` — `reset()` increments `headcountSelectKey.value`,
  forcing Vue to destroy/remount the select on every reset instead of
  reusing the stale instance.

No follow-up issues filed.
