/**
 * Unit tests for the #951 frontend policy helpers — branchOf/isFieldEditable/
 * isRowDeletable. These bucket a row's `source` into the policy branch key
 * the backend payload is keyed by; the actual field matrix lives server-side
 * (data_entry_policies), not duplicated here.
 */

import { test, expect } from '@playwright/test';

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
};

test('branchOf: null/undefined source is user', () => {
  expect(branchOf(null)).toBe('user');
  expect(branchOf(undefined)).toBe('user');
});

test('branchOf: USER_MANUAL (0) is user', () => {
  expect(branchOf(0)).toBe('user');
});

test('branchOf: PLANNER_SNAPSHOT (6) is user', () => {
  expect(branchOf(6)).toBe('user');
});

test('branchOf: any ingestion source is imported', () => {
  for (const source of [1, 2, 3, 4, 5]) {
    expect(branchOf(source)).toBe('imported');
  }
});

test('isFieldEditable: field in the row branch allow-list is editable', () => {
  expect(isFieldEditable(POLICIES, 0, 'sub_class')).toBe(true);
});

test('isFieldEditable: field outside the row branch allow-list is locked', () => {
  expect(isFieldEditable(POLICIES, 1, 'equipment_class')).toBe(false);
});

test('isFieldEditable: null policies (exempt submodule) is never gated', () => {
  expect(isFieldEditable(null, 1, 'anything')).toBe(true);
});

test('isRowDeletable: user row is deletable, imported is not', () => {
  expect(isRowDeletable(POLICIES, 0)).toBe(true);
  expect(isRowDeletable(POLICIES, 1)).toBe(false);
});

test('isRowDeletable: null policies (exempt submodule) is always deletable', () => {
  expect(isRowDeletable(null, 1)).toBe(true);
});
