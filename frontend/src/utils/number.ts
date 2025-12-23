/**
 * Formats a number using Swiss German locale (de-CH)
 * This ensures consistent number formatting throughout the app:
 * - Thousands separator: apostrophe (')
 * - Decimal separator: dot (.)
 *
 * Example: 10750.64 -> "10'750.64"
 *
 * @param value - The number to format
 * @param options - Optional Intl.NumberFormatOptions for customization
 *   - For integers: { minimumFractionDigits: 0, maximumFractionDigits: 0 }
 *   - For specific decimals: { minimumFractionDigits: 2, maximumFractionDigits: 2 }
 * @returns Formatted number string
 */
import { i18n } from 'src/boot/i18n';

const defaultNumberValue = '–';
export function nOrDash(
  value: number | string | null | undefined,
  config?: {
    key?: string;
    locale?: string;
    options?: Intl.NumberFormatOptions;
  },
): string {
  if (value === null || value === undefined || value === '') {
    return defaultNumberValue;
  }
  const numValue = typeof value === 'string' ? Number(value) : value;
  if (!Number.isFinite(numValue)) {
    return defaultNumberValue;
  }
  const {
    key = 'decimal',
    locale = 'de-CH', // i18n.global.locale.value,
    options,
  } = config || {};
  if (options) {
    // @ts-expect-error -- vue-i18n types issue
    return i18n.global.n(numValue, key, locale, options) || defaultNumberValue;
  }
  // @ts-expect-error -- vue-i18n types issue
  return i18n.global.n(numValue, key, locale) || defaultNumberValue;
}
