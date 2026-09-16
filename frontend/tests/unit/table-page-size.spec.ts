/**
 * #2681: module tables take their page size from the module config. Equipment
 * is fixed at 10 rows (a single rows-per-page option hides QTable's selector);
 * every other module keeps the default of 20 with the full list of choices.
 *
 * The Equipment config itself is not imported: it reaches the i18n boot,
 * which the unit runner cannot load. Its values are mirrored inline.
 */

import { test, expect } from '@playwright/test';

import {
  DEFAULT_TABLE_PAGE_SIZE,
  TABLE_PAGE_SIZE_OPTIONS,
} from '../../src/constant/moduleConfig';
import { resolveTablePageSize } from '../../src/utils/tablePageSize';

test('defaults to 20 rows with every option when the config says nothing', () => {
  expect(resolveTablePageSize({})).toEqual({
    rowsPerPage: DEFAULT_TABLE_PAGE_SIZE,
    rowsPerPageOptions: TABLE_PAGE_SIZE_OPTIONS,
  });
});

test('a configured page size keeps the selector when not locked', () => {
  expect(resolveTablePageSize({ tablePageSize: 50 })).toEqual({
    rowsPerPage: 50,
    rowsPerPageOptions: TABLE_PAGE_SIZE_OPTIONS,
  });
});

test('a locked page size offers that single choice only', () => {
  expect(
    resolveTablePageSize({ tablePageSize: 10, tablePageSizeLocked: true }),
  ).toEqual({ rowsPerPage: 10, rowsPerPageOptions: [10] });
});

test('a locked config without an explicit size locks the default', () => {
  expect(resolveTablePageSize({ tablePageSizeLocked: true })).toEqual({
    rowsPerPage: DEFAULT_TABLE_PAGE_SIZE,
    rowsPerPageOptions: [DEFAULT_TABLE_PAGE_SIZE],
  });
});
