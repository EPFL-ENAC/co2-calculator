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
} from '../../src/constant/module-config/traveler-options';

// A fake i18n translate that echoes the key, so we can assert which label wins.
const t = (key: string): string => key;

test('#1153: absent traveler id renders a dash', () => {
  expect(resolveTravelerName(null, undefined, t)).toBe('-');
  expect(resolveTravelerName(undefined, undefined, t)).toBe('-');
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
