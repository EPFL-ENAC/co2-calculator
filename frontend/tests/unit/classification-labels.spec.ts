/**
 * #2401 — table cells for factor-sourced kind/subkind columns resolve
 * their display label from the taxonomy map first (modules that hold the
 * tree — research facilities included — keep their pre-#2401 rendering),
 * then from the row payload's backend-resolved `labels` (purchase, whose
 * tree is never fetched, so its map is empty), then the stored value.
 */

import { test, expect } from '@playwright/test';

import { kindCellLabel } from '../../src/utils/classificationLabels';

test('the taxonomy label wins while the tree is held', () => {
  expect(
    kindCellLabel(
      { researchfacility_id: 'from-resolved-factor' },
      'researchfacility_id',
      { '1902': 'SCITAS-GE' },
      '1902',
    ),
  ).toBe('SCITAS-GE');
});

test('the row label serves modules with no tree (purchase)', () => {
  expect(
    kindCellLabel(
      { purchase_institutional_code: 'Outils électriques' },
      'purchase_institutional_code',
      {},
      '27112700',
    ),
  ).toBe('Outils électriques');
});

test('falls back to the stored value when nothing labels it', () => {
  expect(kindCellLabel(null, 'equipment_class', {}, 'laptop')).toBe('laptop');
});
