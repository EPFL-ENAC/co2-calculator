---
status: in-progress
issue: 2072
last_updated: 2026-08-18
title: "Fix: Enter-key submit leaves a false 'Required' error on the field that was just filled"
summary: "Submitting a module form with the Enter key adds the entry correctly but then flags the focused field as 'Required'. Quasar emits QField's `blur` from a 0 ms timer and QBtn[type=submit] focuses itself on Enter, so ModuleForm's `@blur` validation runs after `reset()` has already cleared the form and validates an empty field the user did fill. Gate blur-validation on fields the user has interacted with since the last reset."
---

# Fix: Enter-key submit shows a false "Required" error (#2072)

## Bug

Reported by @ociccoliniEPFL via @CarolineChereau. In every tool (Calculator,
Planner, Explorer), validating a dynamic-form entry with the **Enter** key
instead of clicking **Add**:

- the entry _is_ created and appears in the table,
- the form clears as expected,
- but the field that had focus is left outlined in red with a **"Required"**
  error under it.

Reproduction from the issue: Explorer → Process emissions → pick `CH₄`, type
`12` in _Quantity (kg)_, press Enter. Confirmed on Firefox, Chrome and Edge —
so it is not browser-specific.

Note what the reported screenshot shows: only _Quantity (kg)_ carries the
error. _Emitted gas_ is equally empty right next to it and is clean. The bug
therefore comes from a **single-field** validation path (blur), not from the
whole-form one (`validateForm()`).

## Root cause

Three behaviours compose into it, two of them inside Quasar (2.24.0):

1. **`ModuleForm.vue:223`** validates a single field on blur:
   `@blur="normalizeField(inp)"` → `normalizeField()` → `validateField()`,
   which sets `errors[id] = $t('validation_required')` for an empty required
   field.
2. **`QBtn` focuses itself when a `type="submit"` click arrives from the
   Enter key** — `node_modules/quasar/src/components/btn/QBtn.js:149-158`,
   comment _"focus button if it came from ENTER on form"_. So Enter moves
   focus off the field the user was typing in, which blurs it. Clicking
   **Add** with the mouse blurs it too, but much earlier (on `mousedown`).
3. **`QField` emits `blur` from a `setTimeout(…, 0)`** —
   `node_modules/quasar/src/composables/private.use-field/use-field.js:359-377`
   (`onControlFocusout`). The native `focusout` is immediate; the `blur` the
   application sees is deferred to the next macrotask.

`QForm.submit()` in turn emits `submit` from inside a promise `.then()`
(`QForm.js:120-129`), i.e. on a **microtask**. Microtasks run before timers,
so the ordering on Enter is:

```
QBtn focuses itself      → native focusout on the input (value "12")
QForm submit             → microtask → onSubmit() → validateForm() passes
                                     → emit('submit') → reset() clears the form
QField's 0 ms timer      → @blur → normalizeField() → validateField()
                                 → field is now empty → "Required"   ← the bug
```

Verified in Chrome against a faithful reproduction of those three behaviours
(a real `<form>`, a submit button that focuses itself on click, a field whose
blur is deferred by `setTimeout(0)`, and a submit handler emitting through a
promise). Logged order:

```
QBtn: focusing self
native focusout, value="12"
QForm emits submit -> onSubmit, value="12"
reset() done, value=""
QField emits blur -> normalizeField/validateField, value=""   <== "Required" set here
```

With a real mouse click on **Add** the 0 ms timer fires in the gap between
`mousedown` and `click`, so blur-validation sees the still-filled field and
the bug does not appear — which is exactly why only the Enter path was
reported.

## Fix

The blur that lands after `reset()` does not describe anything the user did:
the field is empty because _we_ emptied it. So blur-validation only applies
to a field the user has actually interacted with since the form was last
cleared.

- **New** `frontend/src/utils/fieldInteraction.ts` — a small tracker
  (`markInteracted` / `shouldValidateOnBlur` / `clear`), extracted so the
  rule is unit-testable without a browser, mirroring `submitCreateItem.ts`
  (#1463).
- **`ModuleForm.vue`** — `@focus` marks the field interacted, `reset()`
  clears the tracker, and `normalizeField()` skips `validateField()` for a
  field that is not marked. Number normalisation still runs on every blur.

Gating on **focus** (not on `update:model-value`) keeps today's behaviour for
a user who tabs into a required field and leaves it empty: that still shows
"Required" on blur.

The `date` branch needs nothing: it is the one field that uses Quasar's own
`:rules`, and those validate on blur through the same deferred path — but
`reset()` bumps `dateInputKey`, which is in that input's `:key`, so the
component is remounted and the pending validation goes with it.

Not chosen: dropping blur-validation altogether (loses the early feedback on
dates and usage-hours), or a timer-ordering guard released by a second
`setTimeout(0)` (works, but pins behaviour to an implementation detail of
Quasar's internal timer instead of to what the user did).

## Test plan

- `frontend/tests/unit/enter-key-blur-validation.spec.ts` — replays the
  ordered event sequence above against the tracker: a field the user filled
  and submitted with Enter must not be validated by the late blur, while a
  field left empty by the user still must be. Also covers the per-field
  scoping (marking one field does not un-gate its neighbour).

Manual check (needs a working local login, which the current
`backend/.env` does not provide — OAuth is commented out there while the
root `.env` holds the real values):

1. Explorer → Process emissions → pick `CH₄`, type `12` in Quantity, press
   **Enter** → the row is added and no field turns red.
2. Same with the **Add** button → unchanged.
3. Focus Quantity, type nothing, click elsewhere → "Required" still shows.
4. Repeat 1 in the Planner and the Calculator (same component).

## Out of scope

- A Playwright **component** test mounting `ModuleForm` would exercise the
  real Quasar timing end to end, but the CT harness
  (`frontend/playwright/index.ts`) registers no Quasar plugin, no i18n and no
  Pinia, and `ModuleForm` needs all three plus API mocks. Standing it up is
  its own piece of work — worth doing, tracked with the wider
  frontend-validation coverage gap in #1489.
