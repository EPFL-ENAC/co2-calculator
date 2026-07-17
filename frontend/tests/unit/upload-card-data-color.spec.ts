/**
 * Regression test for ``resolveDataButtonColor`` (stage incident
 * 2026-07-17): a WARNING API sync (rows landed, some skipped) fell
 * through to ``accent`` and the data card read "Add Data" / red
 * despite thousands of imported rows — only an explicit API SUCCESS
 * counted. The API result now gets the same ERROR/WARNING/SUCCESS
 * mapping as a CSV result, with CSV precedence preserved (Issue #1216:
 * an errored CSV after a prior API success stays red).
 *
 * Pure ``(dataResult?, apiResult?) => color`` function — a
 * pure-function test is the cheapest regression guard the existing
 * test infra (Playwright, no Vitest) supports; ``useUploadCard`` itself
 * needs a component mount for ``useI18n``.
 */

import { test, expect } from '@playwright/test';
import { resolveDataButtonColor } from '../../src/composables/useUploadCard';
import { IngestionResult } from '../../src/stores/backofficeDataManagement';

test('no jobs at all stays accent (Add Data state)', () => {
  expect(resolveDataButtonColor(undefined, undefined)).toBe('accent');
});

test('API sync results map like CSV results', () => {
  expect(resolveDataButtonColor(undefined, IngestionResult.SUCCESS)).toBe(
    'positive',
  );
  // The incident case: WARNING sync must not render as "no data".
  expect(resolveDataButtonColor(undefined, IngestionResult.WARNING)).toBe(
    'warning',
  );
  expect(resolveDataButtonColor(undefined, IngestionResult.ERROR)).toBe(
    'negative',
  );
});

test('CSV result takes precedence over the API result', () => {
  expect(
    resolveDataButtonColor(IngestionResult.ERROR, IngestionResult.SUCCESS),
  ).toBe('negative');
  expect(
    resolveDataButtonColor(IngestionResult.SUCCESS, IngestionResult.ERROR),
  ).toBe('positive');
});
