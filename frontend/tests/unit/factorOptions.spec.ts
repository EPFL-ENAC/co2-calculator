/**
 * #2007 — options for a select whose stored value is an opaque classification
 * code. Research facility ids read as "1902"; the picker has to show
 * "SCITAS-GE", so options come from the year's factor catalog rather than the
 * class/subclass map (which carries values only).
 */

import { test, expect } from '@playwright/test';

import { toClassOptions } from '../../src/utils/factorOptions';

const COMMON = [
  { researchfacility_id: 1902, researchfacility_name: 'SCITAS-GE' },
  { researchfacility_id: 1012, researchfacility_name: 'CLIMACT-GE' },
];

test('labels by name, keeps the id as the value, sorted by label', () => {
  // ~90 platforms come back in DB order; the picker has to be scannable, and
  // the class/subclass map this replaces was sorted server-side.
  expect(
    toClassOptions(COMMON, 'researchfacility_id', 'researchfacility_name'),
  ).toEqual([
    { label: 'CLIMACT-GE', value: '1012' },
    { label: 'SCITAS-GE', value: '1902' },
  ]);
});

test('one option per facility even with several housing types', () => {
  // Animal factors are keyed (id, name, type) — the same facility appears once
  // per type, but the facility select must offer it a single time.
  const rows = [
    {
      researchfacility_id: '1321',
      researchfacility_name: 'CPG',
      researchfacility_type: 'rodent',
    },
    {
      researchfacility_id: '1321',
      researchfacility_name: 'CPG',
      researchfacility_type: 'fish',
    },
  ];
  expect(
    toClassOptions(rows, 'researchfacility_id', 'researchfacility_name'),
  ).toEqual([{ label: 'CPG', value: '1321' }]);
});

test('drops rows missing either field rather than offering a blank choice', () => {
  const rows = [
    { researchfacility_id: '1', researchfacility_name: null },
    { researchfacility_id: null, researchfacility_name: 'Orphan' },
    { researchfacility_id: '', researchfacility_name: '' },
    { researchfacility_id: '2', researchfacility_name: 'Keeper' },
  ];
  expect(
    toClassOptions(rows, 'researchfacility_id', 'researchfacility_name'),
  ).toEqual([{ label: 'Keeper', value: '2' }]);
});

test('no factors means no options, not a crash', () => {
  expect(
    toClassOptions([], 'researchfacility_id', 'researchfacility_name'),
  ).toEqual([]);
});
