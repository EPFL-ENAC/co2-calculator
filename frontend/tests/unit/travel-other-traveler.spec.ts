/**
 * Regression test for #1153 — "(Travel) Name is not Headcount mandatory".
 *
 * The Travel traveler field is no longer restricted to headcount members: two
 * static "Other traveler" sentinels ("internal" = has a SCIPER, "external" = no
 * SCIPER) can be attributed to a trip. In the table, the traveler name is
 * resolved 100% client-side from `user_institutional_id` via
 * `resolveTravelerName` (used by `ModuleTable.renderCell`). This pins that
 * resolution:
 *   - null/absent id → '-'
 *   - each sentinel → its translated label
 *   - a SCIPER present in this unit's headcount → the member's name
 *   - a SCIPER NOT in the headcount (e.g. imported, doesn't match the CF) →
 *     "Other traveler (internal)" instead of blank (must still remonter).
 */

import { test, expect } from '@playwright/test';

import {
  TRAVELER_OTHER_INTERNAL,
  TRAVELER_OTHER_EXTERNAL,
  TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  resolveTravelerName,
  resolveTravelerCellText,
  travelerSentinelMapEntries,
} from '../../src/constant/module-config/traveler-options';

// A fake i18n translate that echoes the key, so we can assert which label wins.
const t = (key: string): string => key;

test('#1153: no data yet (undefined) renders a dash', () => {
  expect(resolveTravelerName(undefined, undefined, t)).toBe('-');
});

test('#1153: explicit null (External other) resolves to the external label, not a dash', () => {
  expect(resolveTravelerName(null, undefined, t)).toBe(
    TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  );
});

test('#1153: external sentinel renders the external label', () => {
  expect(resolveTravelerName(TRAVELER_OTHER_EXTERNAL, undefined, t)).toBe(
    TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  );
});

test('#1153: internal sentinel renders the internal label', () => {
  expect(resolveTravelerName(TRAVELER_OTHER_INTERNAL, undefined, t)).toBe(
    TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  );
});

test('#1153: SCIPER matching a headcount member renders the member name', () => {
  expect(resolveTravelerName('0184', 'Ada Lovelace', t)).toBe('Ada Lovelace');
});

test('#1153: SCIPER not in the headcount falls back to "Other traveler (internal)"', () => {
  // Imported row whose SCIPER does not match this unit's headcount — it still
  // has a SCIPER, so it is surfaced as internal (not dropped, not blank).
  expect(resolveTravelerName('999999', undefined, t)).toBe(
    TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  );
});

test('#1153: cell text — undefined id (loading) renders a dash', () => {
  expect(
    resolveTravelerCellText(undefined, new Map(), undefined, 'Me', t),
  ).toBe('-');
});

test('#1153: cell text — external sentinel renders the external label', () => {
  expect(resolveTravelerCellText(null, new Map(), undefined, 'Me', t)).toBe(
    TRAVELER_OTHER_EXTERNAL_LABEL_KEY,
  );
});

test('#1153: cell text — internal sentinel renders the internal label', () => {
  expect(
    resolveTravelerCellText(
      TRAVELER_OTHER_INTERNAL,
      new Map(),
      undefined,
      'Me',
      t,
    ),
  ).toBe(TRAVELER_OTHER_INTERNAL_LABEL_KEY);
});

test('#1153: cell text — matching roster entry wins over the raw SCIPER', () => {
  const roster = new Map([['0184', 'Ada Lovelace']]);
  expect(resolveTravelerCellText('0184', roster, undefined, 'Me', t)).toBe(
    'Ada Lovelace',
  );
});

test('#1153: cell text — current user shortcut wins when not in the roster map yet', () => {
  expect(
    resolveTravelerCellText('0184', new Map(), '0184', 'Ada Lovelace', t),
  ).toBe('Ada Lovelace');
});

test('#1153: cell text — unresolved SCIPER falls back to the internal label', () => {
  expect(resolveTravelerCellText('999999', new Map(), undefined, 'Me', t)).toBe(
    TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  );
});

test('#1153: trips-map legend keys external under "" (matches the backend leg coercion)', () => {
  const entries = travelerSentinelMapEntries(t);
  expect(entries).toContainEqual([
    TRAVELER_OTHER_INTERNAL,
    TRAVELER_OTHER_INTERNAL_LABEL_KEY,
  ]);
  expect(entries).toContainEqual(['', TRAVELER_OTHER_EXTERNAL_LABEL_KEY]);
});
