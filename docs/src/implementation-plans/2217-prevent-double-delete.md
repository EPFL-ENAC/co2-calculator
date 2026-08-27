---
status: delivered
issue: 2217
last_updated: 2026-08-27
title: "Prevent double delete in module tables"
summary: "Clicking the delete-confirmation button twice (or pressing Enter twice) before the dialog closed fired two DELETE requests; the second 404'd because the entry was already gone. An in-flight guard in ModuleTable's onConfirmDelete plus a loading state on the submit button makes the second click impossible."
---

# Prevent double delete in module tables (#2217)

## The bug

In `ModuleTable.vue`, the delete-confirmation dialog stays open while
`useModuleStore().deleteItem(...)` is in flight — `confirmDelete` is only set
to `false` in the promise's `.finally`. The submit button (and the form's
Enter handling) remained active during that window, so a fast second click
re-entered `onConfirmDelete` and fired a second `DELETE` for the same row id,
which returned 404 since the first request had already removed the entry.

Repro: open any module page, click a row's delete action, then click the
dialog's Delete button rapidly before the dialog closes.

## The fix

Frontend-only, in `frontend/src/components/organisms/module/ModuleTable.vue`:

- New `deleteInFlight` ref; `onConfirmDelete` returns early when it is set,
  sets it before calling `deleteItem`, and clears it in `.finally` alongside
  the existing dialog close.
- The dialog's submit button gets `:loading="deleteInFlight"` (Quasar's
  loading state also blocks clicks), and the Cancel/close buttons are
  disabled while the request is in flight so the dialog can't be dismissed
  mid-request.

No backend change: the second request no longer happens, and a 404 on a
genuinely missing entry remains a visible error (no silent fallback).
