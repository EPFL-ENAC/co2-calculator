/**
 * The printed reports (#462) must name the unit/affiliation they cover, so a
 * saved PDF stays identifiable once it leaves the browser. These helpers build
 * that label for both flows: the user Results export (one unit, possibly with
 * combined units) and the backoffice export (a filter that can span many).
 */

import { test, expect } from '@playwright/test';

import {
  buildUnitPerimeterLabel,
  buildBackofficeScopeLabel,
  toPrintDocumentTitle,
} from '../../src/utils/unitPerimeterLabel';

/** Stub translator: renders `{named}` placeholders so keys stay assertable. */
const t = (key: string, named?: Record<string, unknown>) =>
  key.replace(/\{(\w+)\}/g, (_, name: string) => String(named?.[name] ?? ''));

const tCounter = (key: string, named?: Record<string, unknown>) => {
  if (key === 'results_combine_units_counter')
    return t('{unit} + {count} units', named);
  if (key === 'print_scope_units_count') return t('{count} units', named);
  return key;
};

test('names the single unit when nothing is combined', () => {
  expect(buildUnitPerimeterLabel('SCI-STI-AB', [], tCounter)).toBe(
    'SCI-STI-AB',
  );
});

test('names both units when exactly one is combined', () => {
  expect(buildUnitPerimeterLabel('SCI-STI-AB', ['ENAC-IIE'], tCounter)).toBe(
    'SCI-STI-AB + ENAC-IIE',
  );
});

test('counts the others beyond two units', () => {
  expect(buildUnitPerimeterLabel('SCI-STI-AB', ['A', 'B', 'C'], tCounter)).toBe(
    'SCI-STI-AB + 3 units',
  );
});

test('backoffice scope names the unit when a single row is exported', () => {
  const rows = [{ unit_name: 'SCI-STI-AB', affiliation: 'STI' }];
  expect(buildBackofficeScopeLabel(rows, tCounter)).toBe('SCI-STI-AB');
});

test('backoffice scope names the affiliation when all rows share one', () => {
  const rows = [
    { unit_name: 'SCI-STI-AB', affiliation: 'STI' },
    { unit_name: 'SCI-STI-CD', affiliation: 'STI' },
  ];
  expect(buildBackofficeScopeLabel(rows, tCounter)).toBe('STI');
});

test('backoffice scope falls back to a count across affiliations', () => {
  const rows = [
    { unit_name: 'SCI-STI-AB', affiliation: 'STI' },
    { unit_name: 'ENAC-IIE-XY', affiliation: 'ENAC' },
  ];
  expect(buildBackofficeScopeLabel(rows, tCounter)).toBe('2 units');
});

test('document title is filename-safe and keeps the scope', () => {
  expect(toPrintDocumentTitle('SCI-STI-AB · 2025', 'Total results')).toBe(
    'Total results_SCI-STI-AB-2025',
  );
});

test('document title falls back to the prefix without a scope', () => {
  expect(toPrintDocumentTitle('', 'Total results')).toBe('Total results');
});
