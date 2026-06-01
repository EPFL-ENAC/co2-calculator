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

export function formatTonnesCO2(
  value: number | string | null | undefined,
): string {
  if (value === null || value === undefined || value === '') {
    return defaultNumberValue;
  }
  const numValue = typeof value === 'string' ? Number(value) : value;
  if (!Number.isFinite(numValue)) {
    return defaultNumberValue;
  }
  const options: Intl.NumberFormatOptions =
    Math.abs(numValue) < 1
      ? { minimumFractionDigits: 1, maximumFractionDigits: 1 }
      : { minimumFractionDigits: 0, maximumFractionDigits: 0 };
  return nOrDash(numValue, { options });
}

export function formatKgCO2(value: number | string | null | undefined): string {
  return nOrDash(value, {
    options: { minimumFractionDigits: 0, maximumFractionDigits: 0 },
  });
}

export function formatFTE(value: number | string | null | undefined): string {
  return nOrDash(value, {
    options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
  });
}

export function formatTonnesForChart(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1) return value.toFixed(0);
  if (abs >= 0.1) return value.toFixed(1);
  return value.toFixed(2);
}

// Auto-scales kg → t past 1000 and appends the unit, e.g. "840 kg CO₂eq" or
// "1.2 t CO₂eq".
export function formatKgCo2eq(kg: number): string {
  if (kg >= 1000) return `${(kg / 1000).toFixed(1)} t CO₂eq`;
  return `${kg.toFixed(0)} kg CO₂eq`;
}

// Rounds up to a "nice" axis-style ceiling (1, 2, 2.5, 5 × 10ⁿ), e.g. 459 → 500
// or 87 → 100 — for tidy legend/scale bounds.
export function niceCeil(value: number): number {
  if (value <= 0) return 0;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  const n = value / magnitude;
  let step = 10;
  if (n <= 1) step = 1;
  else if (n <= 2) step = 2;
  else if (n <= 2.5) step = 2.5;
  else if (n <= 5) step = 5;
  return step * magnitude;
}
