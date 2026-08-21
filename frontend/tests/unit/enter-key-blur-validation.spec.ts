/**
 * Regression test for #2072 — validating an entry with the Enter key left a
 * false "Required" error on the field that was just filled.
 *
 * Three behaviours compose into that bug. `ModuleForm.vue` validates a single
 * field on `@blur`; a Quasar `QBtn[type="submit"]` focuses itself when the
 * browser submits the form on Enter (QBtn.js, "focus button if it came from
 * ENTER on form"), which blurs the field being typed in; and `QField` emits
 * that `blur` from a `setTimeout(…, 0)` (use-field.js, `onControlFocusout`)
 * while `QForm` emits `submit` from a promise. Microtasks run before timers,
 * so the blur handler ran *after* `onSubmit()` had already cleared the form
 * and validated a field the user had in fact filled.
 *
 * `createFieldInteractionTracker` isolates the rule that fixes it — a blur is
 * only worth validating on a field the user put focus in since the form was
 * last cleared — so the ordering can be replayed without a browser.
 */

import { test, expect } from '@playwright/test';

import { createFieldInteractionTracker } from '../../src/utils/fieldInteraction';

test('the blur that lands after an Enter-key submit does not validate the cleared field (#2072)', () => {
  const tracker = createFieldInteractionTracker();

  // The user clicks into Quantity (kg) and types 12.
  tracker.markInteracted('quantity');

  // Enter → QBtn focuses itself → native focusout → QForm's submit microtask
  // runs onSubmit(): the entry is created and reset() clears the form.
  tracker.clear();

  // Only now does QField's 0 ms timer emit `blur`. The field is empty because
  // reset() emptied it, so this blur says nothing about the user's input.
  expect(tracker.shouldValidateOnBlur('quantity')).toBe(false);
});

test('a field the user focused and left empty is still validated on blur', () => {
  const tracker = createFieldInteractionTracker();

  tracker.markInteracted('quantity');

  expect(tracker.shouldValidateOnBlur('quantity')).toBe(true);
});

test('a field is never validated on a blur it never received focus for', () => {
  const tracker = createFieldInteractionTracker();

  // Focus went to the neighbouring select, not to Quantity.
  tracker.markInteracted('category');

  expect(tracker.shouldValidateOnBlur('quantity')).toBe(false);
  expect(tracker.shouldValidateOnBlur('category')).toBe(true);
});

test('interactions survive until the form is cleared, across several fields', () => {
  const tracker = createFieldInteractionTracker();

  tracker.markInteracted('category');
  tracker.markInteracted('subcategory');
  tracker.markInteracted('quantity');

  expect(
    ['category', 'subcategory', 'quantity'].every((id) =>
      tracker.shouldValidateOnBlur(id),
    ),
  ).toBe(true);

  tracker.clear();

  expect(
    ['category', 'subcategory', 'quantity'].some((id) =>
      tracker.shouldValidateOnBlur(id),
    ),
  ).toBe(false);
});
