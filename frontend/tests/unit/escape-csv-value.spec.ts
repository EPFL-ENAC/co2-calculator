/**
 * Regression test (#3185): chart CSV downloads must not hand a spreadsheet a
 * cell it would run as a formula, and must keep negative numbers numeric.
 */
import { test, expect } from 'playwright/test';

import { escapeCsvValue } from '../../src/utils/results-csv';

for (const cell of ['=HYPERLINK(1)', '+1+1', '-1+1', '@SUM(A1)']) {
  test(`neutralizes the formula ${cell}`, () => {
    expect(escapeCsvValue(cell)).toBe(`'${cell}`);
  });
}

test('quotes a neutralized cell that needs quoting', () => {
  expect(escapeCsvValue('=A1,B1')).toBe(`"'=A1,B1"`);
});

test('keeps negative numbers numeric', () => {
  expect(escapeCsvValue(-12.5)).toBe('-12.5');
  expect(escapeCsvValue('-12.5')).toBe('-12.5');
});

test('leaves other values as before', () => {
  expect(escapeCsvValue('plain')).toBe('plain');
  expect(escapeCsvValue('a,b')).toBe('"a,b"');
  expect(escapeCsvValue('say "hi"')).toBe('"say ""hi"""');
  expect(escapeCsvValue(null)).toBe('');
});
