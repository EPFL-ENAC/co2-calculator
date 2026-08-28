/**
 * Regression test for #2473 — `ModuleTable.vue`'s numeric validation rules
 * used non-null assertions (`col.maxDecimals!`) inside closures because the
 * outer `if (col.maxDecimals !== undefined)` narrowing doesn't survive into
 * a nested closure. `getNumericRules` was extracted to `src/utils/` (fixing
 * the assertions by capturing narrowed consts before each closure) so this
 * can be exercised without mounting the component.
 */

import { test, expect } from '@playwright/test';

import { getNumericRules } from '../../src/utils/numeric-rules';

// A fake i18n translate that echoes the key, so we can assert failure vs pass.
const t = (key: string): string => key;

test('#2473: maxDecimals rule passes a value within range and fails one that exceeds it', () => {
  const [, maxDecimalsRule] = getNumericRules({ maxDecimals: 2 }, t);

  expect(maxDecimalsRule('12.34')).toBe(true);
  expect(maxDecimalsRule('12.345')).toBe('validation_max_decimals');
});
