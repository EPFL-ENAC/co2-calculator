/**
 * Regression test — the "EPT par fonction" headcount bar chart showed raw
 * SIUS codes ("51", "52", ...) on its x-axis instead of translated function
 * names, even though the member table and form (same codes) resolved them
 * correctly.
 *
 * Root cause: `HeadCountBarChart.vue` resolved category labels with a plain
 * vue-i18n lookup (`te(key) ? t(key) : key`) against the static locale
 * catalog. `stats` keys are raw SIUS codes (headcount/data_entries.py), never
 * vue-i18n keys, so `te(key)` was always false and the chart fell back to the
 * bare code. The table/form instead resolve the same codes through the
 * backend-seeded member taxonomy vocabulary (#2613). This pins
 * `resolveHeadcountCategoryLabel` — the fix's label lookup — to that same
 * vocabulary-first behaviour.
 *
 * ECharts renders the chart to canvas (no DOM text nodes for axis labels),
 * so the fix is pinned at the label-resolution function itself rather than
 * via a full component mount + DOM assertion.
 */

import { test, expect } from '@playwright/test';

import { resolveHeadcountCategoryLabel } from '../../src/utils/headcountChart';

const vocab = { '51': 'Professors', '57': 'Administrative staff' };

test('a SIUS code known to the taxonomy vocabulary resolves to its label', () => {
  expect(resolveHeadcountCategoryLabel('51', vocab, 'Students')).toBe(
    'Professors',
  );
});

test('a code missing from the vocabulary (not yet loaded) falls back to the bare code, not blank', () => {
  expect(resolveHeadcountCategoryLabel('53', vocab, 'Students')).toBe('53');
});

test('the student sentinel uses its own label, never the vocabulary', () => {
  expect(resolveHeadcountCategoryLabel('student', vocab, 'Students')).toBe(
    'Students',
  );
});
