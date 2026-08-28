/**
 * Regression test for #2473 — `ModuleTable.vue`'s numeric validation rules
 * used non-null assertions (`col.maxDecimals!`) inside closures because the
 * outer `if (col.maxDecimals !== undefined)` narrowing doesn't survive into
 * a nested closure. `getNumericRules` was extracted to `src/utils/` (fixing
 * the assertions by capturing narrowed consts before each closure) so this
 * can be exercised without mounting the component.
 */

import { test, expect } from '@playwright/test';
import { createI18n } from 'vue-i18n';

import { getNumericRules } from '../../src/utils/numeric-rules';
import common from '../../src/i18n/common';

// A fake i18n translate that echoes the key, so we can assert failure vs pass.
const t = (key: string): string => key;

test('#2473: maxDecimals rule passes a value within range and fails one that exceeds it', () => {
  const [, maxDecimalsRule] = getNumericRules({ maxDecimals: 2 }, t);

  expect(maxDecimalsRule('12.34')).toBe(true);
  expect(maxDecimalsRule('12.345')).toBe('validation_max_decimals');
});

/**
 * #2472 — `validation_max_decimals` is parameterized by `{count}` (an
 * arbitrary maxDecimals config value), so it must use vue-i18n's plural
 * pipe rather than hard-coded singular grammar. The echo fake above can't
 * exercise pluralization, so this uses a real Composer (legacy: false,
 * matching boot/i18n.ts) fed only the one key under test.
 */
test('#2472: maxDecimals >= 2 renders a grammatically plural message (en + fr)', () => {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: {
      'en-US': { validation_max_decimals: common.validation_max_decimals.en },
      'fr-CH': { validation_max_decimals: common.validation_max_decimals.fr },
    },
  });

  const [, maxDecimalsRule] = getNumericRules(
    { maxDecimals: 2 },
    i18n.global.t,
  );

  expect(maxDecimalsRule('12.345')).toBe('Must have at most 2 decimal places');

  i18n.global.locale.value = 'fr-CH';
  expect(maxDecimalsRule('12.345')).toBe('Doit avoir maximum 2 décimales');
});
