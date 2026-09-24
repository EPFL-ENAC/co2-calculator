/**
 * Regression guard for #2464: a partial CSV import (one row rejected, the
 * rest stored) used to end in a green "CSV sync completed" toast on the
 * module page. The backend persists row errors under ``meta.stats`` and
 * strips them from the meta root; the live-stream notifier read the root.
 */
import { test, expect } from '@playwright/test';
import { formatJobRowErrors } from '../../src/utils/rowErrors';
import type { JobUpdatePayload } from '../../src/stores/backofficeDataManagement';

const t = (key: string, params?: Record<string, unknown>) =>
  `${key}:${JSON.stringify(params ?? {})}`;

// Shape written by BaseCSVProvider._finalize_and_commit: counts at the
// root, the error list only under ``stats``.
const partialImport: JobUpdatePayload['meta'] = {
  rows_processed: 7,
  rows_skipped: 1,
  row_errors_count: 1,
  stats: {
    row_errors_count: 1,
    row_errors: [
      {
        row: 2,
        reason:
          'fte: Value error, FTE must have at most 1 decimal place(s) (got 0.888)',
      },
    ],
  },
};

test('a skipped row surfaces as a caption with its reason and count', () => {
  const { caption, count } = formatJobRowErrors(partialImport, t);
  expect(count).toBe(1);
  expect(caption).toContain('"row":2');
  expect(caption).toContain('got 0.888');
});

test('a clean import yields no caption', () => {
  const { caption, count } = formatJobRowErrors(
    { rows_processed: 8, rows_skipped: 0, row_errors_count: 0, stats: {} },
    t,
  );
  expect(caption).toBeUndefined();
  expect(count).toBe(0);
});
