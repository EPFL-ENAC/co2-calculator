/**
 * Regression test for #1186 — a traveler can type a station/airport name
 * into the direction-input free-text field without picking an autocomplete
 * suggestion. `form.origin`/`form.destination` (the display text) then
 * looks non-empty and the old "required" check passed, but the identifier
 * the backend actually needs — `origin_iata` for plane, `origin_natural_key`
 * for train — never got set, so the entry silently persisted with zero
 * emissions.
 */
import { test, expect } from '@playwright/test';

import { isTravelLocationResolved } from '../../src/utils/directionLocationValidation';

test('#1186: plane resolves only when origin_iata is set from the autocomplete', () => {
  expect(isTravelLocationResolved('plane', 'GVA', undefined)).toBe(true);
  expect(isTravelLocationResolved('plane', undefined, undefined)).toBe(false);
});

test('#1186: train resolves only when natural_key is set from the autocomplete', () => {
  expect(
    isTravelLocationResolved(
      'train',
      undefined,
      'train:ch:geneva:46.2104:6.1428',
    ),
  ).toBe(true);
  // Typed a name, never picked a suggestion — natural_key stays unset.
  expect(isTravelLocationResolved('train', undefined, undefined)).toBe(false);
});
