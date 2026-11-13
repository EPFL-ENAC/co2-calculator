/**
 * Unit tests for the #951 frontend policy helpers — branchOf/isFieldEditable/
 * isRowDeletable. These bucket a row's `source` into the policy branch key
 * the backend payload is keyed by; the actual field matrix lives server-side
 * (data_entry_policies), not duplicated here. #2646 adds the "reference"
 * branch for Simulator Plan rows priced as a percentage of the reference
 * year.
 */

import { test, expect } from 'playwright/test';

import {
  branchOf,
  isFieldEditable,
  isRowDeletable,
  type DataEntryPolicies,
} from '../../src/utils/dataEntryPolicy';

const POLICIES: DataEntryPolicies = {
  user: { create: true, delete: true, editable_fields: ['sub_class', 'note'] },
  imported: {
    create: false,
    delete: false,
    editable_fields: ['sub_class', 'note'],
  },
  reference: {
    create: false,
    delete: true,
    editable_fields: ['note', 'percentage_of_reference_year'],
  },
};

// A per-line Simulator Plan copy, at 40% of its reference row.
const REFERENCE_ROW = { source: 6, percentage_of_reference_year: 40 };

test('branchOf: null/undefined source is user', () => {
  expect(branchOf({ source: null })).toBe('user');
  expect(branchOf({})).toBe('user');
});

test('branchOf: USER_MANUAL (0) is user', () => {
  expect(branchOf({ source: 0 })).toBe('user');
});

// Professional travel's plain copy (#2018): priced from its own fields.
test('branchOf: PLANNER_SNAPSHOT (6) without a percentage is user', () => {
  expect(branchOf({ source: 6 })).toBe('user');
  expect(branchOf({ source: 6, percentage_of_reference_year: null })).toBe(
    'user',
  );
});

test('branchOf: PLANNER_SNAPSHOT (6) with a percentage is reference', () => {
  expect(branchOf(REFERENCE_ROW)).toBe('reference');
});

// Every per-line copy starts at 0% — a falsy check would leave it editable.
test('branchOf: a 0% snapshot row is still reference', () => {
  expect(branchOf({ source: 6, percentage_of_reference_year: 0 })).toBe(
    'reference',
  );
});

test('branchOf: a percentage on a non-snapshot row is not reference', () => {
  expect(branchOf({ source: 0, percentage_of_reference_year: 50 })).toBe(
    'user',
  );
});

// #2453: an upload into one's OWN module (CSV 2 / API 4) is the operator's
// own data — same rights as manual entry. Only backoffice per-year ingests
// (1, 3, 5) lock.
test('branchOf: unit-specific ingestion source is user', () => {
  for (const source of [2, 4]) {
    expect(branchOf({ source })).toBe('user');
  }
});

test('branchOf: backoffice per-year ingestion source is imported', () => {
  for (const source of [1, 3, 5]) {
    expect(branchOf({ source })).toBe('imported');
  }
});

test('isFieldEditable: field in the row branch allow-list is editable', () => {
  expect(isFieldEditable(POLICIES, { source: 0 }, 'sub_class')).toBe(true);
});

test('isFieldEditable: field outside the row branch allow-list is locked', () => {
  expect(isFieldEditable(POLICIES, { source: 1 }, 'equipment_class')).toBe(
    false,
  );
});

// #2646 regression: sub_class is editable on the user branch, and a slider
// row used to read as user — the cell took an edit that never moved kgCO2eq.
test('isFieldEditable: a reference row keeps only its percentage and note', () => {
  expect(isFieldEditable(POLICIES, REFERENCE_ROW, 'sub_class')).toBe(false);
  expect(
    isFieldEditable(POLICIES, REFERENCE_ROW, 'percentage_of_reference_year'),
  ).toBe(true);
  expect(isFieldEditable(POLICIES, REFERENCE_ROW, 'note')).toBe(true);
});

test('isFieldEditable: null policies (exempt submodule) is never gated', () => {
  expect(isFieldEditable(null, { source: 1 }, 'anything')).toBe(true);
});

test('isRowDeletable: user row is deletable, imported is not', () => {
  expect(isRowDeletable(POLICIES, { source: 0 })).toBe(true);
  expect(isRowDeletable(POLICIES, { source: 1 })).toBe(false);
});

test('isRowDeletable: a reference row stays deletable', () => {
  expect(isRowDeletable(POLICIES, REFERENCE_ROW)).toBe(true);
});

test('isRowDeletable: null policies (exempt submodule) is always deletable', () => {
  expect(isRowDeletable(null, { source: 1 })).toBe(true);
});
