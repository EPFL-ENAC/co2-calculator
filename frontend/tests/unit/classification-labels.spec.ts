/**
 * #2401 — table cells for factor-sourced kind/subkind columns resolve
 * their display label from the row payload first (the backend-localized
 * `labels` map each submodule row now carries), then the taxonomy label
 * map, then the stored value itself. Pins the precedence so purchase's
 * per-row description can never be shadowed by a stale taxonomy map, and
 * rows without labels keep today's fallbacks.
 */

import { test, expect } from '@playwright/test';

import { kindCellLabel } from '../../src/utils/classificationLabels';

test('row-level backend label wins over the taxonomy map', () => {
  expect(
    kindCellLabel(
      { purchase_institutional_code: 'Outils électriques' },
      'purchase_institutional_code',
      { '27112700': 'from-taxonomy' },
      '27112700',
    ),
  ).toBe('Outils électriques');
});

test('falls back to the taxonomy label map when the row carries none', () => {
  expect(
    kindCellLabel(
      undefined,
      'equipment_class',
      { Engine: 'Moteurs' },
      'Engine',
    ),
  ).toBe('Moteurs');
});

test('falls back to the stored value when nothing translates it', () => {
  expect(kindCellLabel(null, 'equipment_class', {}, 'laptop')).toBe('laptop');
});
